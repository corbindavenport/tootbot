import praw
import json
import requests
import tweepy
import time
import os
import csv
import re
import configparser
import urllib.parse
import sys
from glob import glob
from gfycat.client import GfycatClient
from imgurpython import ImgurClient
import distutils.core
import itertools
from PIL import Image
import urllib.request
from mastodon import Mastodon

# Location of the configuration file
CONFIG_FILE = 'config.ini'

def save_file(img_url, file_path):
	resp = requests.get(img_url, stream=True)
	if resp.status_code == 200:
		with open(file_path, 'wb') as image_file:
			for chunk in resp:
				image_file.write(chunk)
		# Return the path of the image, which is always the same since we just overwrite images
		image_file.close()
		return file_path
	else:
		print('[EROR] File failed to download. Status code: ' + str(resp.status_code))
		return

def get_media(img_url, post_id):
	if any(s in img_url for s in ('i.redd.it', 'i.reddituploads.com')):
		file_name = os.path.basename(urllib.parse.urlsplit(img_url).path)
		file_extension = os.path.splitext(img_url)[-1].lower()
		# Fix for issue with i.reddituploads.com links not having a file extension in the URL
		if not file_extension:
			file_extension += '.jpg'
			file_name += '.jpg'
			img_url += '.jpg'
		# Grab the GIF versions of .GIFV links
		# When Tweepy adds support for video uploads, we can use grab the MP4 versions
		if (file_extension == '.gifv'):
			file_extension = file_extension.replace('.gifv', '.gif')
			file_name = file_name.replace('.gifv', '.gif')
			img_url = img_url.replace('.gifv', '.gif')
		# Download the file
		file_path = IMAGE_DIR + '/' + file_name
		print('[ OK ] Downloading file at URL ' + img_url + ' to ' + file_path + ', file type identified as ' + file_extension)
		img = save_file(img_url, file_path)
		return img
	elif ('imgur.com' in img_url): # Imgur
		try:
			client = ImgurClient(IMGUR_CLIENT, IMGUR_CLIENT_SECRET)
		except BaseException as e:
			print ('[EROR] Error while authenticating with Imgur:', str(e))	
			return
		# Working demo of regex: https://regex101.com/r/G29uGl/2
		regex = r"(?:.*)imgur\.com(?:\/gallery\/|\/a\/|\/)(.*?)(?:\/.*|\.|$)"
		m = re.search(regex, img_url, flags=0)
		if m:
			# Get the Imgur image/gallery ID
			id = m.group(1)
			if any(s in img_url for s in ('/a/', '/gallery/')): # Gallery links
				images = client.get_album_images(id)
				# Only the first image in a gallery is used
				imgur_url = images[0].link
			else: # Single image
				imgur_url = client.get_image(id).link
			# If the URL is a GIFV link, change it to a GIF
			file_extension = os.path.splitext(imgur_url)[-1].lower()
			if (file_extension == '.gifv'):
				file_extension = file_extension.replace('.gifv', '.gif')
				img_url = imgur_url.replace('.gifv', '.gif')
			# Download the image
			file_path = IMAGE_DIR + '/' + id + file_extension
			print('[ OK ] Downloading Imgur image at URL ' + imgur_url + ' to ' + file_path)
			imgur_file = save_file(imgur_url, file_path)
			# Imgur will sometimes return a single-frame thumbnail instead of a GIF, so we need to check for this
			if (file_extension == '.gif'):
				# Open the file using the Pillow library
				img = Image.open(imgur_file)
				# Get the MIME type
				mime = Image.MIME[img.format]
				if (mime == 'image/gif'):
					# Image is indeed a GIF, so it can be posted
					img.close()
					return imgur_file
				else:
					# Image is not actually a GIF, so don't post it
					print('[EROR] Imgur has not processed a GIF version of this link, so it can not be posted')
					img.close()
					# Delete the image
					try:
						os.remove(imgur_file)
					except BaseException as e:
						print ('[EROR] Error while deleting media file:', str(e))
					return
			else:
				return imgur_file
		else:
			print('[EROR] Could not identify Imgur image/gallery ID in this URL:', img_url)
			return
	elif ('gfycat.com' in img_url): # Gfycat
		gfycat_name = os.path.basename(urllib.parse.urlsplit(img_url).path)
		client = GfycatClient()
		gfycat_info = client.query_gfy(gfycat_name)
		# Download the 2MB version because Tweepy has a 3MB upload limit for GIFs
		gfycat_url = gfycat_info['gfyItem']['max2mbGif']
		file_path = IMAGE_DIR + '/' + gfycat_name + '.gif'
		print('[ OK ] Downloading Gfycat at URL ' + gfycat_url + ' to ' + file_path)
		gfycat_file = save_file(gfycat_url, file_path)
		return gfycat_file
	elif ('giphy.com' in img_url): # Giphy
		# Working demo of regex: https://regex101.com/r/o8m1kA/2
		regex = r"https?://((?:.*)giphy\.com/media/|giphy.com/gifs/|i.giphy.com/)(.*-)?(\w+)(/|\n)"
		m = re.search(regex, img_url, flags=0)
		if m:
			# Get the Giphy ID
			id = m.group(3)
			# Download the 2MB version because Tweepy has a 3MB upload limit for GIFs
			giphy_url = 'https://media.giphy.com/media/' + id + '/giphy-downsized.gif'
			file_path = IMAGE_DIR + '/' + id + '-downsized.gif'
			print('[ OK ] Downloading Giphy at URL ' + giphy_url + ' to ' + file_path)
			giphy_file = save_file(giphy_url, file_path)
			return giphy_file
		else:
			print('[EROR] Could not identify Giphy ID in this URL:', img_url)
			return
	else:
		# Silently fail when there isn't a media attachment to download
		return

def tweet_creator(subreddit_info):
	post_dict = {}
	print ('[ OK ] Getting posts from Reddit...')
	for submission in subreddit_info.hot(limit=POST_LIMIT):
		if (submission.over_18 and NSFW_POSTS_ALLOWED is False):
			# Skip over NSFW posts if they are disabled in the config file
			print('[ OK ] Skipping', submission.id, 'because it is marked as NSFW')
			continue
		elif (submission.is_self and SELF_POSTS_ALLOWED is False):
			# Skip over NSFW posts if they are disabled in the config file
			print('[ OK ] Skipping', submission.id, 'because it is a self post')
			continue
		else:
			# Set the Twitter max title length for 280, minus the length of the shortlink, minus one for the space between title and shortlink
			twitter_max_title_length = 280 - len(submission.shortlink) - 1
			# Set the Mastodon max title length for 500, minus the length of the shortlink, minus one for the space between title and shortlink
			mastodon_max_title_length = 500 - len(submission.shortlink) - 1
			# Create contents of the Twitter post
			if len(submission.title) < twitter_max_title_length:
				twitter_post = submission.title + ' ' + submission.shortlink
			else:
				twitter_post = submission.title[:max_title_length] + '... ' + submission.shortlink
			# Create contents of the Mastodon post
			if len(submission.title) < mastodon_max_title_length:
				mastodon_post = submission.title + ' ' + submission.shortlink
			else:
				mastodon_post = submission.title[:max_title_length] + '... ' + submission.shortlink
			# Create dict
			post_dict[submission.id] = [twitter_post,mastodon_post,submission.url, submission.id, submission.over_18]
	return post_dict

def setup_connection_reddit(subreddit):
	print ('[ OK ] Setting up connection with Reddit...')
	r = praw.Reddit(
		user_agent='Tootbot',
		client_id=REDDIT_AGENT,
		client_secret=REDDIT_CLIENT_SECRET)
	return r.subreddit(subreddit)

def duplicate_check(id):
	value = False
	with open(CACHE_CSV, 'rt', newline='') as f:
		reader = csv.reader(f, delimiter=',')
		for row in reader:
			if id in row:
				value = True
	f.close()
	return value

def log_post(id, post_url):
	with open(CACHE_CSV, 'a', newline='') as cache:
			date = time.strftime("%d/%m/%Y") + ' ' + time.strftime("%H:%M:%S")
			wr = csv.writer(cache, delimiter=',')
			wr.writerow([id, date, post_url])
	cache.close()

def make_post(post_dict):
	auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
	auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_secret)
	api = tweepy.API(auth)
	for post in post_dict:
		# Grab post details from dictionary
		post_id = post_dict[post][3]
		if not duplicate_check(post_id): # Make sure post is not a duplicate
			file_path = get_media(post_dict[post][2], post_dict[post])
			# Make sure the post contains media (if it doesn't, then file_path would be blank)
			if (((MEDIA_POSTS_ONLY is True) and (file_path)) or (MEDIA_POSTS_ONLY is False)):
				# Post on Twitter
				if ACCESS_TOKEN:
					try:
						auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
						auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_secret)
						twitter = tweepy.API(auth)
						# Post the tweet
						if (file_path):
							print ('[ OK ] Posting this on Twitter account with media attachment:', post_dict[post][0])
							tweet = twitter.update_with_media(filename=file_path, status=post_dict[post][0])
						else:
							print ('[ OK ] Posting this on Twitter account:', post_dict[post][0])
							tweet = twitter.update_status(status=post_dict[post][0])
						# Log the tweet
						log_post(post_id, 'https://twitter.com/' + twitter_username + '/status/' + tweet.id_str + '/')
					except BaseException as e:
						print ('[EROR] Error while posting tweet:', str(e))
						# Log the post anyways
						log_post(post_dict[post][3], 'Error while posting tweet: ' + str(e))
				# Post on Mastodon
				if MASTODON_INSTANCE_DOMAIN:
					try:
						# Post the toot
						if (file_path):
							print ('[ OK ] Posting this on Mastodon account with media attachment:', post_dict[post][1])
							media = mastodon.media_post(file_path, mime_type=None)
							# Add NSFW warning for Reddit posts marked as NSFW
							if (post_dict[post][4] == True):
								toot = mastodon.status_post(post_dict[post][1],media_ids=[media],visibility=MASTODON_POST_VISIBILITY,spoiler_text='NSFW')
							else:	
								toot = mastodon.status_post(post_dict[post][1],media_ids=[media],visibility=MASTODON_POST_VISIBILITY)
						else:
							print ('[ OK ] Posting this on Mastodon account:', post_dict[post][1])
							# Add NSFW warning for Reddit posts marked as NSFW
							if (post_dict[post][4] == True):
								toot = mastodon.status_post(post_dict[post][1],visibility=MASTODON_POST_VISIBILITY,spoiler_text='NSFW')
							else:	
								toot = mastodon.status_post(post_dict[post][1],visibility=MASTODON_POST_VISIBILITY)
						# Log the toot
						log_post(post_id, toot["url"])
					except BaseException as e:
						print ('[EROR] Error while posting toot:', str(e))
						# Log the post anyways
						log_post(post_dict[post][3], 'Error while posting toot: ' + str(e))
				# Cleanup media file
				if (file_path):
					try:
						os.remove(file_path)
						print ('[ OK ] Deleted media file at ' + file_path)
					except BaseException as e:
						print ('[EROR] Error while deleting media file:', str(e))
				# Go to sleep
				print('[ OK ] Sleeping for', DELAY_BETWEEN_TWEETS, 'seconds')
				time.sleep(DELAY_BETWEEN_TWEETS)
			else:
				print ('[ OK ] Ignoring', post_id, 'because non-media posts are disabled or there was not a valid media file downloaded')
		else:
			print ('[ OK ] Ignoring', post_id, 'because it was already posted')

# Check for updates
try:
	with urllib.request.urlopen("https://raw.githubusercontent.com/corbindavenport/tootbot/update-check/current-version.txt") as url:
		s = url.read()
		new_version = s.decode("utf-8").rstrip()
		current_version = 1.0 # Current version of script
		if (current_version < float(new_version)):
			print('[WARN] A new version of Tootbot (' + str(new_version) + ') is available! (you have ' + str(current_version) + ')')
			print ('[WARN] Get the latest update from here: https://github.com/corbindavenport/tootbot/releases')
		else:
			print('[ OK ] You have the latest version of Tootbot (' + str(current_version) + ')')
	url.close()
except BaseException as e:
	print ('[EROR] Error while checking for updates:', str(e))
# Make sure config file exists
try:
	config = configparser.ConfigParser()
	config.read(CONFIG_FILE)
except BaseException as e:
	print ('[EROR] Error while reading config file:', str(e))
	sys.exit()
# General settings
CACHE_CSV = config['BotSettings']['CacheFile']
DELAY_BETWEEN_TWEETS = int(config['BotSettings']['DelayBetweenTweets'])
POST_LIMIT = int(config['BotSettings']['PostLimit'])
SUBREDDIT_TO_MONITOR = config['BotSettings']['SubredditToMonitor']
NSFW_POSTS_ALLOWED = bool(distutils.util.strtobool(config['BotSettings']['NSFWPostsAllowed']))
SELF_POSTS_ALLOWED = bool(distutils.util.strtobool(config['BotSettings']['SelfPostsAllowed']))
# Settings related to media attachments
IMAGE_DIR = config['MediaSettings']['MediaFolder']
MEDIA_POSTS_ONLY = bool(distutils.util.strtobool(config['MediaSettings']['MediaPostsOnly']))
# Twitter API keys
ACCESS_TOKEN = config['Twitter']['AccessToken']
ACCESS_TOKEN_secret = config['Twitter']['AccessTokenSecret']
CONSUMER_KEY = config['Twitter']['ConsumerKey']
CONSUMER_SECRET = config['Twitter']['ConsumerSecret']
# Mastodon info
MASTODON_INSTANCE_DOMAIN = config['Mastodon']['InstanceDomain']
MASTODON_POST_VISIBILITY = config['Mastodon']['PostVisibility']
# Reddit API keys
REDDIT_AGENT = config['Reddit']['Agent']
REDDIT_CLIENT_SECRET = config['Reddit']['ClientSecret']
# Imgur API keys
IMGUR_CLIENT = config['Imgur']['ClientID']
IMGUR_CLIENT_SECRET = config['Imgur']['ClientSecret']
# Log into Twitter if enabled in settings
if ACCESS_TOKEN:
	try:
		auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
		auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_secret)
		twitter = tweepy.API(auth)
		# Make sure authentication is working
		twitter_username = twitter.me().screen_name
		print ('[ OK ] Sucessfully authenticated on Twitter as @' + twitter_username)
	except BaseException as e:
		print ('[EROR] Error while logging into Twitter:', str(e))
		print ('[EROR] Tootbot cannot continue, now shutting down')
		exit()
# Log into Mastodon if enabled in settings
if MASTODON_INSTANCE_DOMAIN:
	if not os.path.exists('mastodon.secret'):
		# If the secret file doesn't exist, it means the setup process hasn't happened yet
		MASTODON_USERNAME = input("[ .. ] Enter email address for Mastodon account: ")
		MASTODON_PASSWORD = input("[ .. ] Enter password for Mastodon account: ")
		print ('[ OK ] Generating login key for Mastodon...')
		try:
			Mastodon.create_app(
				'Tootbot',
				website = 'https://github.com/corbindavenport/tootbot',
				api_base_url = 'https://' + MASTODON_INSTANCE_DOMAIN,
				to_file = 'mastodon.secret'
			)
			mastodon = Mastodon(
				client_id = 'mastodon.secret',
				api_base_url = 'https://' + MASTODON_INSTANCE_DOMAIN
			)
			mastodon.log_in(
				MASTODON_USERNAME,
				MASTODON_PASSWORD,
				to_file = 'mastodon.secret'
			)
			# Make sure authentication is working
			username = mastodon.account_verify_credentials()['username']
			print ('[ OK ] Sucessfully authenticated on ' + MASTODON_INSTANCE_DOMAIN + ' as @' + username + ', login information now stored in mastodon.secret file')
		except BaseException as e:
			print ('[EROR] Error while logging into Mastodon:', str(e))
			print ('[EROR] Tootbot cannot continue, now shutting down')
			exit()
	else:
		try:
			mastodon = Mastodon(
				client_id = 'mastodon.secret',
				access_token = 'mastodon.secret',
				api_base_url = 'https://' + MASTODON_INSTANCE_DOMAIN
			)
			# Make sure authentication is working
			username = mastodon.account_verify_credentials()['username']
			print ('[ OK ] Sucessfully authenticated on ' + MASTODON_INSTANCE_DOMAIN + ' as @' + username)
		except BaseException as e:
			print ('[EROR] Error while logging into Mastodon:', str(e))
			print ('[EROR] Tootbot cannot continue, now shutting down')
			exit()
# Set the command line window title on Windows
if (os.name == 'nt'):
	try:
		if ACCESS_TOKEN and MASTODON_INSTANCE_DOMAIN:
			# Set title with both Twitter and Mastodon usernames
			# Get Twitter username
			twitter_username = twitter.me().screen_name
			# Get Mastodon username
			masto_username = mastodon.account_verify_credentials()['username']
			# Set window title
			title = twitter_username + '@twitter.com and ' + masto_username + '@' + MASTODON_INSTANCE_DOMAIN + ' - Tootbot'
		elif ACCESS_TOKEN:
			# Set title with just Twitter username
			twitter_username = twitter.me().screen_name
			# Set window title
			title = '@' + twitter_username + ' - Tootbot'
		elif MASTODON_INSTANCE_DOMAIN:
			# Set title with just Mastodon username
			masto_username = mastodon.account_verify_credentials()['username']
			# Set window title
			title = masto_username + '@' + MASTODON_INSTANCE_DOMAIN + ' - Tootbot'
	except :
		title = 'Tootbot'
	os.system('title ' + title)
# Run the main script
while True:
	# Make sure logging file and media directory exists
	if not os.path.exists(CACHE_CSV):
		with open(CACHE_CSV, 'w', newline='') as cache:
			default = ['Reddit post ID','Date and time', 'Post link']
			wr = csv.writer(cache)
			wr.writerow(default)
		print ('[ OK ] ' + CACHE_CSV + ' file not found, created a new one')
		cache.close()
	if not os.path.exists(IMAGE_DIR):
		os.makedirs(IMAGE_DIR)
		print ('[ OK ] ' + IMAGE_DIR + ' folder not found, created a new one')
	# Continue with script
	subreddit = setup_connection_reddit(SUBREDDIT_TO_MONITOR)
	post_dict = tweet_creator(subreddit)
	make_post(post_dict)
	print('[ OK ] Sleeping for', DELAY_BETWEEN_TWEETS, 'seconds')
	time.sleep(DELAY_BETWEEN_TWEETS)
	print('[ OK ] Restarting main process...')

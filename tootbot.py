import praw
import json
import tweepy
import time
import os
import csv
import configparser
import urllib.parse
import sys
from imgurpython import ImgurClient
from glob import glob
import distutils.core
import itertools
from mastodon import Mastodon
from getmedia import get_media


def tweet_creator(subreddit_info):
    post_dict = {}
    print('[ OK ] Getting posts from Reddit...')
    for submission in subreddit_info.hot(limit=POST_LIMIT):
        if (submission.over_18 and NSFW_POSTS_ALLOWED is False):
            # Skip over NSFW posts if they are disabled in the config file
            print('[ OK ] Skipping', submission.id,
                  'because it is marked as NSFW')
            continue
        elif (submission.is_self and SELF_POSTS_ALLOWED is False):
            # Skip over NSFW posts if they are disabled in the config file
            print('[ OK ] Skipping', submission.id,
                  'because it is a self post')
            continue
        elif (submission.spoiler and SPOILERS_ALLOWED is False):
            # Skip over posts marked as spoilers if they are disabled in the config file
            print('[ OK ] Skipping', submission.id,
                  'because it is marked as a spoiler')
            continue
        else:
            # Create string of hashtags
            hashtag_string = ''
            if HASHTAGS:
                for x in HASHTAGS:
                    # Add hashtag to string, followed by a space for the next one
                    hashtag_string += '#' + x + ' '
            # Set the Twitter max title length for 280, minus the length of the shortlink and hashtags, minus one for the space between title and shortlink
            twitter_max_title_length = 280 - \
                len(submission.shortlink) - len(hashtag_string) - 1
            # Set the Mastodon max title length for 500, minus the length of the shortlink and hashtags, minus one for the space between title and shortlink
            mastodon_max_title_length = 500 - \
                len(submission.shortlink) - len(hashtag_string) - 1
            # Create contents of the Twitter post
            if len(submission.title) < twitter_max_title_length:
                twitter_post = submission.title + ' ' + hashtag_string + submission.shortlink
            else:
                twitter_post = submission.title[:twitter_max_title_length] + \
                    '... ' + hashtag_string + submission.shortlink
            # Create contents of the Mastodon post
            if len(submission.title) < mastodon_max_title_length:
                mastodon_post = submission.title + ' ' + hashtag_string + submission.shortlink
            else:
                mastodon_post = submission.title[:mastodon_max_title_length] + \
                    '... ' + hashtag_string + submission.shortlink
            # Create dict
            post_dict[submission.id] = [twitter_post, mastodon_post,
                                        submission.url, submission.id, submission.over_18]
    return post_dict


def setup_connection_reddit(subreddit):
    print('[ OK ] Setting up connection with Reddit...')
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
    for post in post_dict:
        # Grab post details from dictionary
        post_id = post_dict[post][3]
        if not duplicate_check(post_id):  # Make sure post is not a duplicate
            file_path = get_media(
                post_dict[post][2], IMGUR_CLIENT, IMGUR_CLIENT_SECRET)
            # Make sure the post contains media (if it doesn't, then file_path would be blank)
            if (((MEDIA_POSTS_ONLY is True) and (file_path)) or (MEDIA_POSTS_ONLY is False)):
                # Post on Twitter
                if POST_TO_TWITTER:
                    try:
                        auth = tweepy.OAuthHandler(
                            CONSUMER_KEY, CONSUMER_SECRET)
                        auth.set_access_token(
                            ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
                        twitter = tweepy.API(auth)
                        # Post the tweet
                        if (file_path):
                            print(
                                '[ OK ] Posting this on Twitter with media attachment:', post_dict[post][0])
                            tweet = twitter.update_with_media(
                                filename=file_path, status=post_dict[post][0])
                        else:
                            print('[ OK ] Posting this on Twitter:',
                                  post_dict[post][0])
                            tweet = twitter.update_status(
                                status=post_dict[post][0])
                        # Log the tweet
                        log_post(post_id, 'https://twitter.com/' +
                                 twitter_username + '/status/' + tweet.id_str + '/')
                    except BaseException as e:
                        print('[EROR] Error while posting tweet:', str(e))
                        # Log the post anyways
                        log_post(post_id,
                                 'Error while posting tweet: ' + str(e))
                # Post on Mastodon
                if MASTODON_INSTANCE_DOMAIN:
                    try:
                        # Post the toot
                        if (file_path):
                            print(
                                '[ OK ] Posting this on Mastodon with media attachment:', post_dict[post][1])
                            media = mastodon.media_post(
                                file_path, mime_type=None)
                            # If the post is marked as NSFW on Reddit, force sensitive media warning for images
                            if (post_dict[post][4] == True):
                                toot = mastodon.status_post(post_dict[post][1], media_ids=[
                                                            media], spoiler_text='NSFW')
                            else:
                                toot = mastodon.status_post(post_dict[post][1], media_ids=[
                                                            media], sensitive=MASTODON_SENSITIVE_MEDIA)
                        else:
                            print('[ OK ] Posting this on Mastodon:',
                                  post_dict[post][1])
                            # Add NSFW warning for Reddit posts marked as NSFW
                            if (post_dict[post][4] == True):
                                toot = mastodon.status_post(
                                    post_dict[post][1], spoiler_text='NSFW')
                            else:
                                toot = mastodon.status_post(post_dict[post][1])
                        # Log the toot
                        log_post(post_id, toot["url"])
                    except BaseException as e:
                        print('[EROR] Error while posting toot:', str(e))
                        # Log the post anyways
                        log_post(post_dict[post][3],
                                 'Error while posting toot: ' + str(e))
                # Cleanup media file
                if (file_path):
                    try:
                        os.remove(file_path)
                        print('[ OK ] Deleted media file at ' + file_path)
                    except BaseException as e:
                        print('[EROR] Error while deleting media file:', str(e))
                # Go to sleep
                print('[ OK ] Sleeping for', DELAY_BETWEEN_TWEETS, 'seconds')
                time.sleep(DELAY_BETWEEN_TWEETS)
            else:
                print('[ OK ] Ignoring', post_id,
                      'because non-media posts are disabled or there was not a valid media file downloaded')
        else:
            print('[ OK ] Ignoring', post_id, 'because it was already posted')


# Check for updates
try:
    with urllib.request.urlopen("https://raw.githubusercontent.com/corbindavenport/tootbot/update-check/current-version.txt") as url:
        s = url.read()
        new_version = s.decode("utf-8").rstrip()
        current_version = 2.3  # Current version of script
        if (current_version < float(new_version)):
            print('[WARN] A new version of Tootbot (' + str(new_version) + ') is available! (you have ' + str(current_version) + ')')
            print('[WARN] Get the latest update from here: https://github.com/corbindavenport/tootbot/releases')
        else:
            print('[ OK ] You have the latest version of Tootbot (' + str(current_version) + ')')
    url.close()
except BaseException as e:
    print('[EROR] Error while checking for updates:', str(e))
# Make sure config file exists
try:
    config = configparser.ConfigParser()
    config.read('config.ini')
except BaseException as e:
    print('[EROR] Error while reading config file:', str(e))
    sys.exit()
# General settings
CACHE_CSV = config['BotSettings']['CacheFile']
DELAY_BETWEEN_TWEETS = int(config['BotSettings']['DelayBetweenPosts'])
POST_LIMIT = int(config['BotSettings']['PostLimit'])
SUBREDDIT_TO_MONITOR = config['BotSettings']['SubredditToMonitor']
NSFW_POSTS_ALLOWED = bool(distutils.util.strtobool(
    config['BotSettings']['NSFWPostsAllowed']))
SPOILERS_ALLOWED = bool(distutils.util.strtobool(
    config['BotSettings']['SpoilersAllowed']))
SELF_POSTS_ALLOWED = bool(distutils.util.strtobool(
    config['BotSettings']['SelfPostsAllowed']))
if config['BotSettings']['Hashtags']:
    # Parse list of hashtags
    HASHTAGS = config['BotSettings']['Hashtags']
    HASHTAGS = [x.strip() for x in HASHTAGS.split(',')]
else:
    HASHTAGS = ''
# Settings related to media attachments
MEDIA_POSTS_ONLY = bool(distutils.util.strtobool(
    config['MediaSettings']['MediaPostsOnly']))
# Twitter info
POST_TO_TWITTER = bool(distutils.util.strtobool(
    config['Twitter']['PostToTwitter']))
# Mastodon info
MASTODON_INSTANCE_DOMAIN = config['Mastodon']['InstanceDomain']
MASTODON_SENSITIVE_MEDIA = bool(
    distutils.util.strtobool(config['Mastodon']['SensitiveMedia']))
# Setup and verify Reddit access
if not os.path.exists('reddit.secret'):
    print('[WARN] API keys for Reddit not found. Please enter them below (see wiki if you need help).')
    # Whitespaces are stripped from input: https://stackoverflow.com/a/3739939
    REDDIT_AGENT = ''.join(input("[ .. ] Enter Reddit agent: ").split())
    REDDIT_CLIENT_SECRET = ''.join(
        input("[ .. ] Enter Reddit client secret: ").split())
    # Make sure authentication is working
    try:
        reddit_client = praw.Reddit(
            user_agent='Tootbot', client_id=REDDIT_AGENT, client_secret=REDDIT_CLIENT_SECRET)
        test = reddit_client.subreddit('announcements')
        # It worked, so save the keys to a file
        reddit_config = configparser.ConfigParser()
        reddit_config['Reddit'] = {
            'Agent': REDDIT_AGENT,
            'ClientSecret': REDDIT_CLIENT_SECRET
        }
        with open('reddit.secret', 'w') as f:
            reddit_config.write(f)
        f.close()
    except BaseException as e:
        print('[EROR] Error while logging into Reddit:', str(e))
        print('[EROR] Tootbot cannot continue, now shutting down')
        exit()
else:
    # Read API keys from secret file
    reddit_config = configparser.ConfigParser()
    reddit_config.read('reddit.secret')
    REDDIT_AGENT = reddit_config['Reddit']['Agent']
    REDDIT_CLIENT_SECRET = reddit_config['Reddit']['ClientSecret']
# Setup and verify Imgur access
if not os.path.exists('imgur.secret'):
    print('[WARN] API keys for Imgur not found. Please enter them below (see wiki if you need help).')
    # Whitespaces are stripped from input: https://stackoverflow.com/a/3739939
    IMGUR_CLIENT = ''.join(input("[ .. ] Enter Imgur client ID: ").split())
    IMGUR_CLIENT_SECRET = ''.join(
        input("[ .. ] Enter Imgur client secret: ").split())
    # Make sure authentication is working
    try:
        imgur_client = ImgurClient(IMGUR_CLIENT, IMGUR_CLIENT_SECRET)
        test_gallery = imgur_client.get_album('dqOyj')
        # It worked, so save the keys to a file
        imgur_config = configparser.ConfigParser()
        imgur_config['Imgur'] = {
            'ClientID': IMGUR_CLIENT,
            'ClientSecret': IMGUR_CLIENT_SECRET
        }
        with open('imgur.secret', 'w') as f:
            imgur_config.write(f)
        f.close()
    except BaseException as e:
        print('[EROR] Error while logging into Imgur:', str(e))
        print('[EROR] Tootbot cannot continue, now shutting down')
        exit()
else:
    # Read API keys from secret file
    imgur_config = configparser.ConfigParser()
    imgur_config.read('imgur.secret')
    IMGUR_CLIENT = imgur_config['Imgur']['ClientID']
    IMGUR_CLIENT_SECRET = imgur_config['Imgur']['ClientSecret']
# Log into Twitter if enabled in settings
if POST_TO_TWITTER is True:
    if os.path.exists('twitter.secret'):
        # Read API keys from secret file
        twitter_config = configparser.ConfigParser()
        twitter_config.read('twitter.secret')
        ACCESS_TOKEN = twitter_config['Twitter']['AccessToken']
        ACCESS_TOKEN_SECRET = twitter_config['Twitter']['AccessTokenSecret']
        CONSUMER_KEY = twitter_config['Twitter']['ConsumerKey']
        CONSUMER_SECRET = twitter_config['Twitter']['ConsumerSecret']
        try:
            # Make sure authentication is working
            auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
            auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
            twitter = tweepy.API(auth)
            twitter_username = twitter.me().screen_name
            print('[ OK ] Sucessfully authenticated on Twitter as @' +
                  twitter_username)
        except BaseException as e:
            print('[EROR] Error while logging into Twitter:', str(e))
            print('[EROR] Tootbot cannot continue, now shutting down')
            exit()
    else:
        # If the secret file doesn't exist, it means the setup process hasn't happened yet
        print('[WARN] API keys for Twitter not found. Please enter them below (see wiki if you need help).')
        # Whitespaces are stripped from input: https://stackoverflow.com/a/3739939
        ACCESS_TOKEN = ''.join(
            input('[ .. ] Enter access token for Twitter account: ').split())
        ACCESS_TOKEN_SECRET = ''.join(
            input('[ .. ] Enter access token secret for Twitter account: ').split())
        CONSUMER_KEY = ''.join(
            input('[ .. ] Enter consumer key for Twitter account: ').split())
        CONSUMER_SECRET = ''.join(
            input('[ .. ] Enter consumer secret for Twitter account: ').split())
        print('[ OK ] Attempting to log in to Twitter...')
        try:
            # Make sure authentication is working
            auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
            auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
            twitter = tweepy.API(auth)
            twitter_username = twitter.me().screen_name
            print('[ OK ] Sucessfully authenticated on Twitter as @' +
                  twitter_username)
            # It worked, so save the keys to a file
            twitter_config = configparser.ConfigParser()
            twitter_config['Twitter'] = {
                'AccessToken': ACCESS_TOKEN,
                'AccessTokenSecret': ACCESS_TOKEN_SECRET,
                'ConsumerKey': CONSUMER_KEY,
                'ConsumerSecret': CONSUMER_SECRET
            }
            with open('twitter.secret', 'w') as f:
                twitter_config.write(f)
            f.close()
        except BaseException as e:
            print('[EROR] Error while logging into Twitter:', str(e))
            print('[EROR] Tootbot cannot continue, now shutting down')
            exit()
# Log into Mastodon if enabled in settings
if MASTODON_INSTANCE_DOMAIN:
    if not os.path.exists('mastodon.secret'):
        # If the secret file doesn't exist, it means the setup process hasn't happened yet
        print('[WARN] API keys for Mastodon not found. Please enter them below (see wiki if you need help).')
        MASTODON_USERNAME = input(
            "[ .. ] Enter email address for Mastodon account: ")
        MASTODON_PASSWORD = input(
            "[ .. ] Enter password for Mastodon account: ")
        print('[ OK ] Generating login key for Mastodon...')
        try:
            Mastodon.create_app(
                'Tootbot',
                website='https://github.com/corbindavenport/tootbot',
                api_base_url='https://' + MASTODON_INSTANCE_DOMAIN,
                to_file='mastodon.secret'
            )
            mastodon = Mastodon(
                client_id='mastodon.secret',
                api_base_url='https://' + MASTODON_INSTANCE_DOMAIN
            )
            mastodon.log_in(
                MASTODON_USERNAME,
                MASTODON_PASSWORD,
                to_file='mastodon.secret'
            )
            # Make sure authentication is working
            masto_username = mastodon.account_verify_credentials()['username']
            print('[ OK ] Sucessfully authenticated on ' + MASTODON_INSTANCE_DOMAIN + ' as @' +
                  masto_username + ', login information now stored in mastodon.secret file')
        except BaseException as e:
            print('[EROR] Error while logging into Mastodon:', str(e))
            print('[EROR] Tootbot cannot continue, now shutting down')
            exit()
    else:
        try:
            mastodon = Mastodon(
                client_id='mastodon.secret',
                access_token='mastodon.secret',
                api_base_url='https://' + MASTODON_INSTANCE_DOMAIN
            )
            # Make sure authentication is working
            username = mastodon.account_verify_credentials()['username']
            print('[ OK ] Sucessfully authenticated on ' +
                  MASTODON_INSTANCE_DOMAIN + ' as @' + username)
        except BaseException as e:
            print('[EROR] Error while logging into Mastodon:', str(e))
            print('[EROR] Tootbot cannot continue, now shutting down')
            exit()
# Set the command line window title on Windows
if (os.name == 'nt'):
    try:
        if POST_TO_TWITTER and MASTODON_INSTANCE_DOMAIN:
            # Set title with both Twitter and Mastodon usernames
            # twitter_username = twitter.me().screen_name
            masto_username = mastodon.account_verify_credentials()['username']
            os.system('title ' + twitter_username + '@twitter.com and ' +
                      masto_username + '@' + MASTODON_INSTANCE_DOMAIN + ' - Tootbot')
        elif POST_TO_TWITTER:
            # Set title with just Twitter username
            twitter_username = twitter.me().screen_name
            os.system('title ' + '@' + twitter_username + ' - Tootbot')
        elif MASTODON_INSTANCE_DOMAIN:
            # Set title with just Mastodon username
            masto_username = mastodon.account_verify_credentials()['username']
            os.system('title ' + masto_username + '@' +
                      MASTODON_INSTANCE_DOMAIN + ' - Tootbot')
    except:
        os.system('title Tootbot')
# Run the main script
while True:
    # Make sure logging file and media directory exists
    if not os.path.exists(CACHE_CSV):
        with open(CACHE_CSV, 'w', newline='') as cache:
            default = ['Reddit post ID', 'Date and time', 'Post link']
            wr = csv.writer(cache)
            wr.writerow(default)
        print('[ OK ] ' + CACHE_CSV + ' file not found, created a new one')
        cache.close()
    # Continue with script
    try:
        subreddit = setup_connection_reddit(SUBREDDIT_TO_MONITOR)
        post_dict = tweet_creator(subreddit)
        make_post(post_dict)
    except BaseException as e:
        print('[EROR] Error in main process:', str(e))
    print('[ OK ] Sleeping for', DELAY_BETWEEN_TWEETS, 'seconds')
    time.sleep(DELAY_BETWEEN_TWEETS)
    print('[ OK ] Restarting main process...')

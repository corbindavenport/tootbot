import praw
import json
import tweepy
import time
import os
import configparser
import urllib.parse
import sys
from imgurpython import ImgurClient
from glob import glob
import distutils.core
import itertools
import redis
from mastodon import Mastodon
from getmedia import get_media


def get_reddit_posts(subreddit_info):
    post_dict = {}
    print('[ OK ] Getting posts from Reddit...')
    for submission in subreddit_info.hot(limit=POST_LIMIT):
        if (submission.over_18 and NSFW_POSTS_ALLOWED is False):
            # Skip over NSFW posts if they are disabled in the config file
            print('[ OK ] Skipping', submission.id, 'because it is marked as NSFW')
            continue
        elif (submission.is_self and SELF_POSTS_ALLOWED is False):
            # Skip over NSFW posts if they are disabled in the config file
            print('[ OK ] Skipping', submission.id, 'because it is a self post')
            continue
        elif (submission.spoiler and SPOILERS_ALLOWED is False):
            # Skip over posts marked as spoilers if they are disabled in the config file
            print('[ OK ] Skipping', submission.id, 'because it is marked as a spoiler')
            continue
        elif (submission.stickied):
            print('[ OK ] Skipping', submission.id, 'because it is stickied')
            continue
        else:
            # Create dict
            post_dict[submission.id] = submission
    return post_dict


def get_twitter_caption(submission):
    # Create string of hashtags
    hashtag_string = ''
    if HASHTAGS:
        for x in HASHTAGS:
            # Add hashtag to string, followed by a space for the next one
            hashtag_string += '#' + x + ' '
    # Set the Twitter max title length for 280, minus the length of the shortlink and hashtags, minus one for the space between title and shortlink
    twitter_max_title_length = 280 - len(submission.shortlink) - len(hashtag_string) - 1
    # Create contents of the Twitter post
    if len(submission.title) < twitter_max_title_length:
        twitter_caption = submission.title + ' ' + hashtag_string + submission.shortlink
    else:
        twitter_caption = submission.title[:twitter_max_title_length] + '... ' + hashtag_string + submission.shortlink
    return twitter_caption

def get_mastodon_caption(submission):
    # Create string of hashtags
    hashtag_string = ''
    if HASHTAGS:
        for x in HASHTAGS:
            # Add hashtag to string, followed by a space for the next one
            hashtag_string += '#' + x + ' '
    # Set the Mastodon max title length for 500, minus the length of the shortlink and hashtags, minus one for the space between title and shortlink
    mastodon_max_title_length = 500 - len(submission.shortlink) - len(hashtag_string) - 1
    # Create contents of the Mastodon post
    if len(submission.title) < mastodon_max_title_length:
        mastodon_caption = submission.title + ' ' + hashtag_string + submission.shortlink
    else:
        mastodon_caption = submission.title[:mastodon_max_title_length] + '... ' + hashtag_string + submission.shortlink
    return mastodon_caption


def setup_connection_reddit(subreddit):
    print('[ OK ] Setting up connection with Reddit...')
    r = praw.Reddit(
        user_agent='Tootbot',
        client_id=REDDIT_AGENT,
        client_secret=REDDIT_CLIENT_SECRET)
    return r.subreddit(subreddit)


def duplicate_check(id):
    r = redis.from_url(os.environ.get("REDIS_URL"))
    if r.get(id):
        return True
    else:
        return False


def log_post(id):
    r = redis.from_url(os.environ.get("REDIS_URL"))
    r.set(id, 'true')


def make_post(post_dict):
    for post in post_dict:
        # Grab post details from dictionary
        post_id = post_dict[post].id
        if not duplicate_check(post_id):  # Make sure post is not a duplicate
            # Download Twitter-compatible version of media file (static image or GIF under 3MB)
            if POST_TO_TWITTER:
                media_file = get_media(post_dict[post].url, IMGUR_CLIENT, IMGUR_CLIENT_SECRET)
            # Download Mastodon-compatible version of media file (static image or MP4 file)
            #if MASTODON_INSTANCE_DOMAIN:
            #    hd_media_file = get_hd_media(post_dict[post], IMGUR_CLIENT, IMGUR_CLIENT_SECRET)
            # Post on Twitter
            if POST_TO_TWITTER:
                # Make sure the post contains media, if MEDIA_POSTS_ONLY in config is set to True
                if (((MEDIA_POSTS_ONLY is True) and media_file) or (MEDIA_POSTS_ONLY is False)):
                    try:
                        auth = tweepy.OAuthHandler(
                            CONSUMER_KEY, CONSUMER_SECRET)
                        auth.set_access_token(
                            ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
                        twitter = tweepy.API(auth)
                        # Generate post caption
                        caption = get_twitter_caption(post_dict[post])
                        # Post the tweet
                        if (media_file):
                            print(
                                '[ OK ] Posting this on Twitter with media attachment:', caption)
                            tweet = twitter.update_with_media(filename=media_file, status=caption)
                            # Clean up media file
                            try:
                                os.remove(media_file)
                                print('[ OK ] Deleted media file at', media_file)
                            except BaseException as e:
                                print('[EROR] Error while deleting media file:', str(e))
                        else:
                            print('[ OK ] Posting this on Twitter:',caption)
                            tweet = twitter.update_status(status=caption)
                        # Log the tweet
                        log_post(post_id)
                    except BaseException as e:
                        print('[EROR] Error while posting tweet:', str(e))
                        # Log the post anyways
                        log_post(post_id)
                else:
                    print('[WARN] Twitter: Ignoring', post_id, 'because non-media posts are disabled or the media file was not found')
            
            # Post on Mastodon
            #TODO: Mastodon support
            
            # Go to sleep
            print('[ OK ] Sleeping for', DELAY_BETWEEN_TWEETS, 'seconds')
            time.sleep(DELAY_BETWEEN_TWEETS)
        else:
            print('[ OK ] Ignoring', post_id, 'because it was already posted')


# Check for updates
try:
    with urllib.request.urlopen("https://raw.githubusercontent.com/corbindavenport/tootbot/update-check/current-version.txt") as url:
        s = url.read()
        new_version = s.decode("utf-8").rstrip()
        current_version = 2.4  # Current version of script
        if (current_version < float(new_version)):
            print('[WARN] A new version of Tootbot (' + str(new_version) + ') is available! (you have ' + str(current_version) + ')')
            print('[WARN] Get the latest update from here: https://github.com/corbindavenport/tootbot/releases')
        else:
            print('[ OK ] You have the latest version of Tootbot (' + str(current_version) + ')')
    url.close()
except BaseException as e:
    print('[EROR] Error while checking for updates:', str(e))
# Connect to Redis database
try:
    r = redis.from_url(os.environ.get("REDIS_URL"))
except BaseException as e:
    print('[EROR] Error while connecting to Redis:', str(e))
    print('[EROR] Tootbot cannot continue, now shutting down')
    exit()
# General settings
DELAY_BETWEEN_TWEETS = int(os.environ.get('DELAY_BETWEEN_POSTS', None))
POST_LIMIT = int(os.environ.get('POST_LIMIT', None))
SUBREDDIT_TO_MONITOR = os.environ.get('SUBREDDIT_TO_MONITOR', None)
NSFW_POSTS_ALLOWED = bool(distutils.util.strtobool(
    os.environ.get('NSFW_POSTS_ALLOWED', None)))
SPOILERS_ALLOWED = bool(distutils.util.strtobool(
    os.environ.get('SPOILERS_ALLOWED', None)))
SELF_POSTS_ALLOWED = bool(distutils.util.strtobool(
    os.environ.get('SELF_POSTS_ALLOWED', None)))
if os.environ.get('HASHTAGS', None) == 'false':
    print('[ OK ] No hashtags configured in settings.')
    HASHTAGS = ''
else:
    # Parse list of hashtags
    HASHTAGS = os.environ.get('HASHTAGS', None)
    HASHTAGS = [x.strip() for x in HASHTAGS.split(',')]
# Settings related to media attachments
MEDIA_POSTS_ONLY = bool(distutils.util.strtobool(
    os.environ.get('MEDIA_POSTS_ONLY', None)))
# Reddit info
REDDIT_AGENT = os.environ.get('REDDIT_AGENT', None)
REDDIT_CLIENT_SECRET = os.environ.get('REDDIT_SECRET', None)
# Imgur info
IMGUR_CLIENT = os.environ.get('IMGUR_ID', None)
IMGUR_CLIENT_SECRET = os.environ.get('IMGUR_SECRET', None)
# Log into Twitter if enabled in settings
POST_TO_TWITTER = bool(distutils.util.strtobool(
    os.environ.get('POST_TO_TWITTER', None)))
if POST_TO_TWITTER is True:
    print('[ OK ] Attempting to log in to Twitter...')
    # Read API keys from environment variables
    try:
        ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN', None)
        ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET', None)
        CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY', None)
        CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET', None)
    except BaseException as e:
        print('[EROR] Error while reading Twitter API tokens:', str(e))
        print('[EROR] Please see the Tootbot wiki for full setup instructions.')
        print('[EROR] Tootbot cannot continue, now shutting down')
        exit()
    try:
        # Make sure authentication is working
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        twitter = tweepy.API(auth)
        twitter_username = twitter.me().screen_name
        print('[ OK ] Sucessfully authenticated on Twitter as @' + twitter_username)
    except BaseException as e:
        print('[EROR] Error while logging into Twitter:', str(e))
        print('[EROR] Tootbot cannot continue, now shutting down')
        exit()
# Log into Mastodon if enabled in settings
POST_TO_MASTODON = bool(distutils.util.strtobool(
    os.environ.get('POST_TO_MASTODON', None)))
if POST_TO_MASTODON is True:
    #TODO: Implement Mastodon support with variables MASTODON_INSTANCE_DOMAIN and MASTODON_SENSITIVE_MEDIA
    print('[WARN] Mastodon posting is enabled, but Mastodon posting has not yet been implemented in the Heroku version of Tootbot.')
# Run the main script
while True:
    subreddit = setup_connection_reddit(SUBREDDIT_TO_MONITOR)
    post_dict = get_reddit_posts(subreddit)
    make_post(post_dict)
    print('[ OK ] Sleeping for', DELAY_BETWEEN_TWEETS, 'seconds')
    time.sleep(DELAY_BETWEEN_TWEETS)
    print('[ OK ] Restarting main process...')

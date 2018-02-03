# Tootbot

This is a Python bot that looks up posts from specified subreddits and automatically posts them on Twitter and/or [Mastodon](https://joinmastodon.org/). It is based on [reddit-twitter-bot](https://github.com/rhiever/reddit-twitter-bot). Tootbot was created for the [@ItMeIRL](https://twitter.com/ItMeIRL) Twitter account, and is now used on a variety of other accounts.

**Features:**

* Posting to both Twitter and [Mastodon](https://joinmastodon.org/)
* Media from Gfycat, Imgur, and Giphy will be automatically attached in the social media post
* Can ignore links that do not contain media, ideal for meme accounts like [@ItMeIRL](https://twitter.com/ItMeIRL)
* NSFW content and self-posts can be filtered
* Can monitor multiple subreddits at once
* Fully open-source and runs locally, so you don't have to give an external service full access to your social media account(s)

## Disclaimer

The developers of Tootbot hold no liability for what you do with this script or what happens to you by using this script. Abusing this script *can* get you banned from Twitter, so make sure to read up on proper usage of the Twitter API.

## Dependencies

First, you will need to install Python 3 on your system. After that, you will need to install the [tweepy](https://github.com/tweepy/tweepy), [PRAW](https://praw.readthedocs.io/en/latest/), [py-gfycat](https://github.com/ankeshanand/py-gfycat), [imgurpython](https://github.com/Imgur/imgurpython), [Pillow](https://github.com/python-pillow/Pillow), and [Mastodon.py](https://github.com/halcy/Mastodon.py) libraries.

You can install all dependencies by running this one command:

    pip3 install tweepy praw gfycat imgurpython PhotoHash Pillow Mastodon.py

## Setting up the bot

All settings for the bot can be found in the `config.ini` file. Open the file in any text editor and add the following info:

1. Under the [BotSettings] section, add the name of the subreddit to `SubredditToMonitor` (do not include the /r/). You can also set multiple subreddits using the `+` symbol (example: `AnimalsBeingBros+babyelephantgifs+aww`).
2. By default, the bot will wait at least 600 seconds between tweets to prevent spamming. You can change this by editing the `DelayBetweenTweets` setting in the `[BotSettings]` section.
3. By default, the bot will only look at the top 10 'hot' posts in a subreddit. You can change this by editing the `PostLimit` setting in the `[BotSettings]` section.

Next, you'll need to give Tootbot access to a Twitter account, and add the required information to the config file.

1. [Sign in](https://dev.twitter.com/apps) with the Twitter account you want to use with the bot
2. Click the 'Create New App' button
3. Fill out the Name, Description, and Website fields with anything you want (you can leave the callback field blank)
4. Make sure that 'Access level' says 'Read and write'
5. Click the 'Keys and Access Tokens' tab
6. Click the 'Create my access token' button
7. Fill out the `[PrimaryTwitterKeys]` section in the config file with the info

In addition, you will have to create an application on Reddit:

1. Sign in with your Reddit account
2. Go to your [app preferences](https://www.reddit.com/prefs/apps) and create a new application at the bottom
3. Select the application type as 'script'
4. Add the token (seen below the name of the bot after it's generated) and the secret to the [Reddit] section of the config file

Finally, you need to create an application on Imgur, so the bot can obtain direct image links from Imgur posts and albums:

1. Sign into [Imgur](https://imgur.com/) with your account, or make one if you haven't already.
2. Register an application [here](https://api.imgur.com/oauth2/addclient). Choose 'OAuth 2 authorization without a callback URL' as the app type.
3. Add the Client ID and Client secret to the `[Imgur]` section of the config file

## Usage

Once you edit the bot script to provide the necessary API keys and the subreddit you want to tweet from, you can run the bot on the command line:

    python tootbot.py

# Tootbot

**I am no longer actively developing Tootbot, and no bug fixes or new features will be implemented. There a fork developed by Mark Burgunder [here](https://gitlab.com/marvin8/tootbot), with fixes to Gfycat integration and and other changes.**

This is a Python bot that looks up posts from specified subreddits and automatically posts them on Twitter and/or [Mastodon](https://joinmastodon.org/). It is based on [reddit-twitter-bot](https://github.com/rhiever/reddit-twitter-bot). Tootbot is now used by [a wide variety of social media accounts](https://github.com/corbindavenport/tootbot/wiki/Accounts-using-Tootbot).

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

**Features:**

* Can post to both Twitter and [Mastodon](https://joinmastodon.org/)
* Runs in the cloud with a free Heroku account, or locally on any PC with Python
* Media from direct links, Gfycat, Imgur, Reddit, and Giphy is automatically attached in the social media post
* Links that do not contain media can be skipped, ideal for meme accounts
* NSFW content, spoilers, and self-posts can be filtered
* Multiple subreddits can be monitored at once

Tootbot uses the [tweepy](https://github.com/tweepy/tweepy), [PRAW](https://praw.readthedocs.io/en/latest/), [py-gfycat](https://github.com/ankeshanand/py-gfycat), [imgurpython](https://github.com/Imgur/imgurpython), [Pillow](https://github.com/python-pillow/Pillow), and [Mastodon.py](https://github.com/halcy/Mastodon.py) libraries. The Heroku version also uses the [redis-py](https://github.com/andymccurdy/redis-py) library.

## Disclaimer

The developers of Tootbot hold no liability for what you do with this script or what happens to you by using this script. Abusing this script *can* get you banned from Twitter and/or Mastodon, so make sure to read up on proper usage of the API for each site.

## Setup and usage

For instructions on setting up and using Tootbot, please visit [the wiki](https://github.com/corbindavenport/tootbot/wiki).

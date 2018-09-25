import os
import sys
import configparser
from gfycat.client import GfycatClient
from imgurpython import ImgurClient
from PIL import Image
import urllib.request
from urllib.request import urlopen
import requests
import re
import hashlib

# Function for opening file as string of bytes

def file_as_bytes(file):
    with file:
        return file.read()

# Function for downloading images from a URL to media folder

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
        print('[EROR] File failed to download. Status code: ' +
              str(resp.status_code))
        return

# Function for obtaining static images and GIFs from popular image hosts

def get_media(img_url, IMGUR_CLIENT, IMGUR_CLIENT_SECRET):
  # Make sure config file exists
  try:
      config = configparser.ConfigParser()
      config.read('config.ini')
  except BaseException as e:
      print('[EROR] Error while reading config file:', str(e))
      sys.exit()
  # Make sure media folder exists
  IMAGE_DIR = config['MediaSettings']['MediaFolder']
  if not os.path.exists(IMAGE_DIR):
      os.makedirs(IMAGE_DIR)
      print('[ OK ] Media folder not found, created a new one')
  # Download and save the linked image
  if any(s in img_url for s in ('i.redd.it', 'i.reddituploads.com')):  # Reddit-hosted images
      file_name = os.path.basename(urllib.parse.urlsplit(img_url).path)
      file_extension = os.path.splitext(img_url)[-1].lower()
      # Fix for issue with i.reddituploads.com links not having a file extension in the URL
      if not file_extension:
          file_extension += '.jpg'
          file_name += '.jpg'
          img_url += '.jpg'
      # Download the file
      file_path = IMAGE_DIR + '/' + file_name
      print('[ OK ] Downloading file at URL ' + img_url + ' to ' +
            file_path + ', file type identified as ' + file_extension)
      img = save_file(img_url, file_path)
      return img
  elif ('v.redd.it' in img_url):  # Reddit video
      print ('[WARN] Reddit videos can not be uploaded to Twitter, due to API limitations')
      return
  elif ('imgur.com' in img_url):  # Imgur
      try:
          client = ImgurClient(IMGUR_CLIENT, IMGUR_CLIENT_SECRET)
      except BaseException as e:
          print('[EROR] Error while authenticating with Imgur:', str(e))
          return
      # Working demo of regex: https://regex101.com/r/G29uGl/2
      regex = r"(?:.*)imgur\.com(?:\/gallery\/|\/a\/|\/)(.*?)(?:\/.*|\.|$)"
      m = re.search(regex, img_url, flags=0)
      if m:
          # Get the Imgur image/gallery ID
          id = m.group(1)
          if any(s in img_url for s in ('/a/', '/gallery/')):  # Gallery links
              images = client.get_album_images(id)
              # Only the first image in a gallery is used
              imgur_url = images[0].link
          else:  # Single image
              imgur_url = client.get_image(id).link
          # If the URL is a GIFV or MP4 link, change it to the GIF version
          file_extension = os.path.splitext(imgur_url)[-1].lower()
          if (file_extension == '.gifv'):
              file_extension = file_extension.replace('.gifv', '.gif')
              imgur_url = imgur_url.replace('.gifv', '.gif')
          elif (file_extension == '.mp4'):
              file_extension = file_extension.replace('.mp4', '.gif')
              imgur_url = imgur_url.replace('.mp4', '.gif')
          # Download the image
          file_path = IMAGE_DIR + '/' + id + file_extension
          print('[ OK ] Downloading Imgur image at URL ' +
                imgur_url + ' to ' + file_path)
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
                  print('[WARN] Imgur has not processed a GIF version of this link, so it can not be posted to Twitter')
                  img.close()
                  # Delete the image
                  try:
                      os.remove(imgur_file)
                  except BaseException as e:
                      print('[EROR] Error while deleting media file:', str(e))
                  return
          else:
              return imgur_file
      else:
          print(
              '[EROR] Could not identify Imgur image/gallery ID in this URL:', img_url)
          return
  elif ('gfycat.com' in img_url):  # Gfycat
      gfycat_name = os.path.basename(urllib.parse.urlsplit(img_url).path)
      client = GfycatClient()
      gfycat_info = client.query_gfy(gfycat_name)
      # Download the 2MB version because Tweepy has a 3MB upload limit for GIFs
      gfycat_url = gfycat_info['gfyItem']['max2mbGif']
      file_path = IMAGE_DIR + '/' + gfycat_name + '.gif'
      print('[ OK ] Downloading Gfycat at URL ' +
            gfycat_url + ' to ' + file_path)
      gfycat_file = save_file(gfycat_url, file_path)
      return gfycat_file
  elif ('giphy.com' in img_url):  # Giphy
      # Working demo of regex: https://regex101.com/r/o8m1kA/2
      regex = r"https?://((?:.*)giphy\.com/media/|giphy.com/gifs/|i.giphy.com/)(.*-)?(\w+)(/|\n)"
      m = re.search(regex, img_url, flags=0)
      if m:
          # Get the Giphy ID
          id = m.group(3)
          # Download the 2MB version because Tweepy has a 3MB upload limit for GIFs
          giphy_url = 'https://media.giphy.com/media/' + id + '/giphy-downsized.gif'
          file_path = IMAGE_DIR + '/' + id + '-downsized.gif'
          print('[ OK ] Downloading Giphy at URL ' +
                giphy_url + ' to ' + file_path)
          giphy_file = save_file(giphy_url, file_path)
          # Check the hash to make sure it's not a GIF saying "This content is not available"
          # More info: https://github.com/corbindavenport/tootbot/issues/8
          hash = hashlib.md5(file_as_bytes(
              open(giphy_file, 'rb'))).hexdigest()
          if (hash == '59a41d58693283c72d9da8ae0561e4e5'):
              print('[WARN] Giphy has not processed a 2MB GIF version of this link, so it can not be posted to Twitter')
              return
          else:
              return giphy_file
      else:
          print('[EROR] Could not identify Giphy ID in this URL:', img_url)
          return
  else:
      # Check if URL is an image, based on the MIME type
      image_formats = ('image/png', 'image/jpeg', 'image/gif', 'image/webp')
      img_site = urlopen(img_url)
      meta = img_site.info()
      if meta["content-type"] in image_formats:
          # URL appears to be an image, so download it
          file_name = os.path.basename(urllib.parse.urlsplit(img_url).path)
          file_path = IMAGE_DIR + '/' + file_name
          print('[ OK ] Downloading file at URL ' +
                img_url + ' to ' + file_path)
          try:
              img = save_file(img_url, file_path)
              return img
          except BaseException as e:
              print('[EROR] Error while downloading image:', str(e))
              return
      else:
          print('[EROR] URL does not point to a valid image file')
          return

# Function for obtaining static images/GIFs, or MP4 videos if they exist, from popular image hosts
# This is currently only used for Mastodon posts, because the Tweepy API doesn't support video uploads


def get_hd_media(submission, IMGUR_CLIENT, IMGUR_CLIENT_SECRET):
  media_url = submission.url
  # Make sure config file exists
  try:
      config = configparser.ConfigParser()
      config.read('config.ini')
  except BaseException as e:
      print('[EROR] Error while reading config file:', str(e))
      sys.exit()
  # Make sure media folder exists
  IMAGE_DIR = config['MediaSettings']['MediaFolder']
  if not os.path.exists(IMAGE_DIR):
      os.makedirs(IMAGE_DIR)
      print('[ OK ] Media folder not found, created a new one')
  # Download and save the linked image
  if any(s in media_url for s in ('i.redd.it', 'i.reddituploads.com')):  # Reddit-hosted images
      file_name = os.path.basename(urllib.parse.urlsplit(media_url).path)
      file_extension = os.path.splitext(media_url)[-1].lower()
      # Fix for issue with i.reddituploads.com links not having a file extension in the URL
      if not file_extension:
          file_extension += '.jpg'
          file_name += '.jpg'
          media_url += '.jpg'
      # Download the file
      file_path = IMAGE_DIR + '/' + file_name
      print('[ OK ] Downloading file at URL ' + media_url + ' to ' +
            file_path + ', file type identified as ' + file_extension)
      img = save_file(media_url, file_path)
      return img
  elif ('v.redd.it' in media_url):  # Reddit video
      if submission.media:
          # Get URL for MP4 version of reddit video
          video_url = submission.media['reddit_video']['fallback_url']
          # Download the file
          file_path = IMAGE_DIR + '/' + submission.id + '.mp4'
          print('[ OK ] Downloading Reddit video at URL ' +
                video_url + ' to ' + file_path)
          video = save_file(video_url, file_path)
          return video
      else:
          print('[EROR] Reddit API returned no media for this URL:', media_url)
          return
  elif ('imgur.com' in media_url):  # Imgur
      try:
          client = ImgurClient(IMGUR_CLIENT, IMGUR_CLIENT_SECRET)
      except BaseException as e:
          print('[EROR] Error while authenticating with Imgur:', str(e))
          return
      # Working demo of regex: https://regex101.com/r/G29uGl/2
      regex = r"(?:.*)imgur\.com(?:\/gallery\/|\/a\/|\/)(.*?)(?:\/.*|\.|$)"
      m = re.search(regex, media_url, flags=0)
      if m:
          # Get the Imgur image/gallery ID
          id = m.group(1)
          if any(s in media_url for s in ('/a/', '/gallery/')):  # Gallery links
              images = client.get_album_images(id)
              # Only the first image in a gallery is used
              imgur_url = images[0].link
              print(images[0])
          else:  # Single image/GIF
              if client.get_image(id).type == 'image/gif':
                  # If the image is a GIF, use the MP4 version
                  imgur_url = client.get_image(id).mp4
              else:
                  imgur_url = client.get_image(id).link
          file_extension = os.path.splitext(imgur_url)[-1].lower()
          # Download the image
          file_path = IMAGE_DIR + '/' + id + file_extension
          print('[ OK ] Downloading Imgur image at URL ' +
                imgur_url + ' to ' + file_path)
          imgur_file = save_file(imgur_url, file_path)
          return imgur_file
      else:
          print(
              '[EROR] Could not identify Imgur image/gallery ID in this URL:', media_url)
          return
  elif ('gfycat.com' in media_url):  # Gfycat
      gfycat_name = os.path.basename(urllib.parse.urlsplit(media_url).path)
      client = GfycatClient()
      gfycat_info = client.query_gfy(gfycat_name)
      # Download the Mp4 version
      gfycat_url = gfycat_info['gfyItem']['mp4Url']
      file_path = IMAGE_DIR + '/' + gfycat_name + '.mp4'
      print('[ OK ] Downloading Gfycat at URL ' +
            gfycat_url + ' to ' + file_path)
      gfycat_file = save_file(gfycat_url, file_path)
      return gfycat_file
  elif ('giphy.com' in media_url):  # Giphy
      # Working demo of regex: https://regex101.com/r/o8m1kA/2
      regex = r"https?://((?:.*)giphy\.com/media/|giphy.com/gifs/|i.giphy.com/)(.*-)?(\w+)(/|\n)"
      m = re.search(regex, media_url, flags=0)
      if m:
          # Get the Giphy ID
          id = m.group(3)
          # Download the MP4 version of the GIF
          giphy_url = 'https://media.giphy.com/media/' + id + '/giphy.mp4'
          file_path = IMAGE_DIR + '/' + id + 'giphy.mp4'
          print('[ OK ] Downloading Giphy at URL ' +
                giphy_url + ' to ' + file_path)
          giphy_file = save_file(giphy_url, file_path)
          return giphy_file
      else:
          print('[EROR] Could not identify Giphy ID in this URL:', media_url)
          return
  else:
      # Check if URL is an image or MP4 file, based on the MIME type
      image_formats = ('image/png', 'image/jpeg',
                        'image/gif', 'image/webp', 'video/mp4')
      img_site = urlopen(media_url)
      meta = img_site.info()
      if meta["content-type"] in image_formats:
          # URL appears to be an image, so download it
          file_name = os.path.basename(urllib.parse.urlsplit(media_url).path)
          file_path = IMAGE_DIR + '/' + file_name
          print('[ OK ] Downloading file at URL ' +
                media_url + ' to ' + file_path)
          try:
              img = save_file(media_url, file_path)
              return img
          except BaseException as e:
              print('[EROR] Error while downloading image:', str(e))
              return
      else:
          print('[EROR] URL does not point to a valid image file.')
          return

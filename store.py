#!/usr/bin/python3
# Bucketcam: limited best effort image storage
# Copyright (C) 2024 Bram Neijt

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from PIL import Image, ImageFilter
import io
import logging
import os.path
import configparser
import urllib.request
import sys
import datetime
import shutil
import hashlib
import random

logging.basicConfig(level = logging.INFO, format = '%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

class UTC(datetime.tzinfo):
  """UTC"""

  def utcoffset(self, dt):
    return datetime.timedelta(0)

  def tzname(self, dt):
    return "UTC"

  def dst(self, dt):
    return datetime.timedelta(0)

def hashOfFile(filename):
    buffSize = 1024*100
    hasher = hashlib.sha1()
    with open(filename, 'rb') as afile:
        buff = afile.read(buffSize)
        while len(buff) > 0:
            hasher.update(buff)
            buff = afile.read(buffSize)
    return hasher.hexdigest()

def loadCameraImage(config):
    url = config.get("source", "imageDownloadUrl")

    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()

    username = config.get("source", "basicAuthUser")
    password = config.get("source", "basicAuthPass")
    password_mgr.add_password(None, url, username, password)

    handler = urllib.request.HTTPDigestAuthHandler(password_mgr)

    opener = urllib.request.build_opener(handler)
    r = opener.open(url)
    return r.read()

def meanValue(image):
    #General value of image
    return image.convert("L").resize((1,1)).getpixel((0,0))

def countRed(image):
    #Number of colors used in image
    assert image.mode == "RGB"
    data = image.resize((100,100)).getdata(band = 0)
    return len(set(data))

def countGreen(image):
    #Number of colors used in image
    assert image.mode == "RGB"
    data = image.resize((100,100)).getdata(band = 1)
    return len(set(data))

def countBlue(image):
    #Number of colors used in image
    assert image.mode == "RGB"
    data = image.resize((100,100)).getdata(band = 2)
    return len(set(data))

def edgeValueForQuadrant(quadrantIndex):
    def q(image):
        edges = image.filter(ImageFilter.FIND_EDGES)
        w, h = image.size
        quadrants = (
          (0, 0, w // 2, h // 2),
          (w // 2, 0, w, h // 2),
          (0, h // 2, w // 2, h),
          (w // 2, h // 2, w, h)
         )
        return edges.crop(quadrants[quadrantIndex]).resize((1,1)).getpixel((0,0))
    return q
    
def randomValue(image):
    return random.randint(0, 1000)


def logStorage(filename):
    imageTimestamp = datetime.datetime.now(UTC())
    imageHash = hashOfFile(filename)
    logFilename = "images/storage_%s.log" % imageTimestamp.strftime("%Y-%m-%d")
    with open(logFilename, "a") as storageLog:
        storageLog.write("%s %s %s\n" % (imageTimestamp.isoformat(), imageHash, filename))

class LevelOfDetail(object):
    def __init__(self, levels):
        assert isinstance(levels, list)
        assert len(levels) >= 1
        logger.debug("LOD with levels %s", repr(levels))
        self.levels =  levels

    @staticmethod
    def fromImageAtLevel(image, toplevel):
        levels = []
        for l in range(toplevel + 1):
            levels.append(LevelOfDetail.imageTagAtLevel(image, l))
        return LevelOfDetail(levels)

    @staticmethod
    def imageTagAtLevel(image, level):
        levels = [
            meanValue,
            countRed,
            countGreen,
            countBlue,
            edgeValueForQuadrant(3),
            edgeValueForQuadrant(2),
            edgeValueForQuadrant(1),
            edgeValueForQuadrant(0),
            randomValue
        ]
        assert level < len(levels)
        v = str(levels[level](image))
        return v

    def remove(self):
        #Remove anything already there
        path = self.path()
        if os.path.exists(path):
            logger.info("Removing %s", path)
            shutil.rmtree(path)
        if os.path.exists(path + ".jpg"):
            logger.info("Removing %s", path + ".jpg")
            os.unlink(path + ".jpg")

    def getLevel(self):
        return len(self.levels) -1

    def isOccupied(self):
        loc = self.path()
        return os.path.exists(loc) or os.path.exists(loc + ".jpg")

    def hasBranched(self):
        loc = self.path()
        return os.path.exists(loc) and os.path.isdir(loc)

    def store(self, image):
        self.remove()
        path = self.path()
        directory = os.path.dirname(path)
        if len(directory) and not os.path.exists(directory):
            os.makedirs(directory)
        loc = path + ".jpg"
        image.save(loc)
        logStorage(loc)

    def branch(self):
        self.remove()
        loc = self.path()
        if not os.path.exists(loc):
            os.makedirs(loc)

    def path(self):
        return os.path.join("images", *self.levels)

def loadImage(config):
    logger.info("Loading image")
    imageData = io.BytesIO(loadCameraImage(config))
    return Image.open(imageData)

def loadConfig():
    config = configparser.ConfigParser()
    config.read('bucketcam.ini')
    return config

def main():
    config = loadConfig()

    #Load image
    image = loadImage(config)
    lod = LevelOfDetail.fromImageAtLevel(image, 0)
    while lod.hasBranched():
        lod = LevelOfDetail.fromImageAtLevel(image, lod.getLevel() + 1)

    maxNumberOfImages = config.getint('storage', 'numberOfImages')
    logger.info("Counting number of images already stored")
    imagesStored = sum([len(dpf[2]) for dpf in os.walk("images")])
    logger.info("Found %i stored out of a maximum of %i", imagesStored, maxNumberOfImages)
    moreImagesAllowed = imagesStored < maxNumberOfImages

    if lod.isOccupied():
        #There is an image already stored here. If more images are allowed, branch, otherwise overwrite
        if moreImagesAllowed:
            #Branch to store the extra image
            logger.info("Branching and increasing level")
            lod.branch()
            lod = LevelOfDetail.fromImageAtLevel(image, lod.getLevel() + 1)
            lod.store(image)
        else:
            #No more images allowed, just overwrite the image or directory
            lod.store(image)
    else:
        #There is no image here, if we store here we get another image
        if moreImagesAllowed:
            lod.store(image)
        else:
            #No more images allowed, prune the branch by going up one and storing there
            lod = LevelOfDetail.fromImageAtLevel(image, lod.getLevel() - 1)
            lod.store(image)
    return 0

if __name__ == "__main__":
    sys.exit(main())

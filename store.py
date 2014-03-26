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
    '''Different values of green
    used in the image'''
    assert image.mode == "RGB"
    data = image.resize((100,100)).getdata(band = 1)
    return len(set(data))

def countBlue(image):
    '''Different values of blue
    used in the image'''
    assert image.mode == "RGB"
    data = image.resize((100,100)).getdata(band = 2)
    return len(set(data))

def binaryPixelCount(image):
    '''Number of pixels that fall in to the first of two categories
    when the image has been converted to two colors'''
    return image.convert("L").quantize(2).histogram()[0]


def edgeValueForQuadrant(quadrantIndex):
    def q(image):
        edges = image.filter(ImageFilter.FIND_EDGES).convert("L")
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

LEVELS_OF_DETAIL = [
    meanValue,
    countRed,
    countGreen,
    countBlue,
    edgeValueForQuadrant(3),
    edgeValueForQuadrant(2),
    edgeValueForQuadrant(1),
    edgeValueForQuadrant(0),
    binaryPixelCount
]

class StorageLimit(object):
    def __init__(self, limit):
        self._useCount = 0
        self.limit = limit
    def hasLimitBeenReached(self):
        return self._useCount >= self.limit
    def loadFromDisk(self):
        self._useCount = sum([len(dpf[2]) for dpf in os.walk("images")])
    def getUsed(self):
        return self._useCount
    def usedAndLimit(self):
        return (self._useCount, self.limit)
    def inc(self, amount):
        self._useCount += amount
        return self._useCount
    def dec(self, amount):
        self._useCount -= amount
        return self._useCount

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
        assert level < len(LEVELS_OF_DETAIL)
        v = str(LEVELS_OF_DETAIL[level](image))
        return v

    def remove(self, storageLimit):
        #Remove anything already there
        path = self.path()
        removeCount = 0
        if os.path.exists(path):
            assert os.path.isdir(path)
            logger.debug("Removing %s", path)
            for (root, dirnames, files) in os.walk(top, topdown=False):
                removeCount += len(files)
                map(os.unlink, [os.path.join(root, name) for name in files])
            for (path, dirnames, files) in os.walk(top, topdown=False):
                map(os.rmdir, [os.path.join(root, name) for name in dirnames])
        if os.path.exists(path + ".jpg"):
            logger.debug("Removing %s", path + ".jpg")
            os.unlink(path + ".jpg")
            removeCount += 1
        logger.debug("Removed %i files", removeCount)
        storageLimit.dec(removeCount)
        return removeCount

    def getLevel(self):
        return len(self.levels) -1

    def isOccupied(self):
        loc = self.path()
        return os.path.exists(loc) or os.path.exists(loc + ".jpg")

    def hasBranched(self):
        loc = self.path()
        return os.path.exists(loc) and os.path.isdir(loc)

    def store(self, image, storageLimit):
        self.remove(storageLimit)
        path = self.path()
        directory = os.path.dirname(path)
        if len(directory) and not os.path.exists(directory):
            os.makedirs(directory)
        loc = path + ".jpg"
        image.save(loc)
        storageLimit.inc(1)
        logStorage(loc)

    def branch(self, storageLimit):
        '''Branch at the current level

        This transforms an image into a directory.
        We have to remove the image because the change of removing
        the branch in the future is minimal because the main function
        aggresively enters branches on collisions.
        
        If the current level of detail is the maximum level of detail,
        branching will fail and return false. It returns true otherwise.
        '''
        if len(self.levels) >= len(LEVELS_OF_DETAIL):
            return False
        self.remove(storageLimit)
        loc = self.path()
        if not os.path.exists(loc):
            os.makedirs(loc)
        return True

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
    storageLimit = StorageLimit(maxNumberOfImages)
    storageLimit.loadFromDisk()
    logger.info("Storage limit at %i out of %i" % storageLimit.usedAndLimit())

    if lod.isOccupied():
        #There is an image already stored here. If more images are allowed, branch, otherwise overwrite
        if storageLimit.hasLimitBeenReached():
            #Branch if possible
            if lod.branch():
                logger.info("Branching into level %i", lod.getLevel() + 1)
                lod = LevelOfDetail.fromImageAtLevel(image, lod.getLevel() + 1)
            else:
                logger.warn("More images allowed, but no more levels of detail left")
            lod.store(image, storageLimit)
        else:
            #No more images allowed, just overwrite the image or directory
            lod.store(image, storageLimit)
    else:
        #There is no image here, if we store here we get another image
        if storageLimit.hasLimitBeenReached():
            lod.store(image, storageLimit)
        else:
            if lod.getLevel() > 0:
                #No more images allowed, prune the branch by going up one and storing there
                lod = LevelOfDetail.fromImageAtLevel(image, lod.getLevel() - 1)
            else:
                logger.warning("Should be pruning, but that has not been implemented yet")
                logger.error("Probably exceeding limit because of excess storage in level 0")
            lod.store(image, storageLimit)
    return 0

if __name__ == "__main__":
    sys.exit(main())

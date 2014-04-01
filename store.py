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
import arrow
import numpy.fft
import math

logging.basicConfig(level = logging.INFO, format = '%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

def hashOfFile(filename):
    buffSize = 1024*100
    hasher = hashlib.sha1()
    with open(filename, 'rb') as afile:
        buff = afile.read(buffSize)
        while len(buff) > 0:
            hasher.update(buff)
            buff = afile.read(buffSize)
    return hasher.hexdigest()


class ImageLoader(object):
    def __init__(self, config):
        self.config = config
    def __iter__(self):
        while True:
            yield self.loadCameraImage(self.config)
    def loadCameraImage(self, config):
        # return Image.open("original.png")
        url = config.get("source", "imageDownloadUrl")

        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()

        username = config.get("source", "basicAuthUser")
        password = config.get("source", "basicAuthPass")
        password_mgr.add_password(None, url, username, password)

        handler = urllib.request.HTTPDigestAuthHandler(password_mgr)

        opener = urllib.request.build_opener(handler)
        r = opener.open(url)
        imageData = io.BytesIO(r.read())
        return Image.open(imageData)


def logStorage(filename):
    imageTimestamp = arrow.get()
    imageHash = hashOfFile(filename)
    logFilename = "images/storage_%s.log" % imageTimestamp.strftime("%Y-%m-%d")
    with open(logFilename, "a") as storageLog:
        storageLog.write("%s %s %s\n" % (imageTimestamp.isoformat(), imageHash, filename))

def readLogStorage(filename):
    with open(filename, "r") as storageLog:
        for line in storageLog.readlines():
            (isoTime, hashWhenStored, filename) = line.split(" ", 2)
            yield {
                "datetime": arrow.get(isoTime).to('local'),
                "hash": hashWhenStored,
                "filename": filename.strip()
            }

class StorageLimit(object):
    '''Simple storage limit counter'''
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
    def __init__(self, image, desiredLevelCount):
        assert hasattr(image, "convert")
        #Calculate the resize needed to get around the desiredLevelCount
        size = math.ceil(math.sqrt(desiredLevelCount))
        levels =  [abs(i) for i in numpy.fft.rfft( image.convert("L").resize((size, size)).getdata() )]
        levels = levels[1:] #Throw away the first level (mean intensity)
        logger.debug("FFT resulted in %i levels", len(levels))
        maxEntriesPerDirectory = 1024
        normalizationFactor = maxEntriesPerDirectory / max(levels)
        self.levels = [int(round((normalizationFactor * i))) for i in levels]
        logger.debug("Done calculating FFT")

    def toLevel(self, level):
        assert level >= 0
        assert level < len(self.levels)
        self.level = level

    def currentLevels(self):
        return self.levels[:self.level + 1]

    def remove(self, storageLimit):
        #Remove anything already there
        path = self.path()
        removeCount = 0
        if os.path.exists(path):
            assert os.path.isdir(path)
            logger.debug("Removing %s", path)
            for (root, dirnames, files) in os.walk(path, topdown = True):
                removeCount += len(files)
                logger.debug("Removing %s", repr(files))
                for name in files:
                    os.unlink(os.path.join(root, name))
            for (root, dirnames, files) in os.walk(path, topdown = False):
                for name in dirnames:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(path)
        if os.path.exists(path + ".jpg"):
            logger.debug("Removing %s", path + ".jpg")
            os.unlink(path + ".jpg")
            removeCount += 1
        logger.debug("Removed %i file", removeCount)
        storageLimit.dec(removeCount)
        return removeCount

    def getLevel(self):
        return self.level

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
        logger.debug("Storing %s", loc)
        image.save(loc)
        storageLimit.inc(1)
        logStorage(loc)

    def hasMoreLevels(self):
        return self.level < len(self.levels)

    def branch(self, storageLimit):
        '''Branch at the current level

        This transforms an image into a directory.
        We have to remove the image because the change of removing
        the branch in the future is minimal because the main function
        aggresively enters branches on collisions.
        '''
        self.remove(storageLimit)
        loc = self.path()
        if not os.path.exists(loc):
            os.makedirs(loc)


    def path(self):
        return os.path.join("images", *[ str(l) for l in self.currentLevels()])


def loadConfig():
    config = configparser.ConfigParser()
    config.read('bucketcam.ini')
    return config



def loadAndStoreImage(image, storageLimit):
    logger.info("Storage limit at %i out of %i" % storageLimit.usedAndLimit())
    #Load image
    desiredLevelCount = 30
    lod = LevelOfDetail(image, desiredLevelCount)
    lod.toLevel(0)
    while lod.hasBranched() and lod.hasMoreLevels():
        lod.toLevel(lod.getLevel() + 1)



    if storageLimit.hasLimitBeenReached():
        #If there is an image, we can just overwrite it
        #If there is no image there, and we are at a higher level.
        # We need to start pruning this branch
        if lod.getLevel() > 0:
            logger.warning("Moving down one level of detail to save storage space")
            lod.toLevel(lod.getLevel() - 1)
        elif not lod.isOccupied():
            logger.warning("Should be doing some kind of level 0 random pruning")
            logger.error("Probably exceeding limit because of excess storage in level 0")
        #In the end, we have to store
        lod.store(image, storageLimit)
    else:
        if lod.isOccupied():
            #Just branch if there is a collision and we have more levels
            # because storage limit has not been reached yet
            if lod.hasMoreLevels():
                lod.branch(storageLimit)
                logger.debug("Branching succeeded into level %i", lod.getLevel() + 1)
                lod.toLevel(lod.getLevel() + 1)
            else:
                logger.warn("More images allowed, but no more levels of detail left")
        lod.store(image, storageLimit)

def main():
    config = loadConfig()

    maxNumberOfImages = config.getint('storage', 'numberOfImages')
    storageLimit = StorageLimit(maxNumberOfImages)
    imageLoader = ImageLoader(config)
    storageLimit.loadFromDisk()
    for image in imageLoader:
        loadAndStoreImage(image, storageLimit)
    return 0

if __name__ == "__main__":
    sys.exit(main())

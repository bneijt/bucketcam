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


from PIL import Image
# import http.client
# import base64
import io
import logging
import os.path
import configparser
import urllib.request
import sys
# import datetime

logging.basicConfig(level = logging.DEBUG, format = '%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

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

import shutil


class LevelOfDetail(object):
    def __init__(self, levels):
        assert isinstance(levels, list)
        assert len(levels) >= 1
        logger.info("LOD with levels %s", repr(levels))
        self.levels =  levels

    @staticmethod
    def fromImageAtLevel(image, toplevel):
        levels = [LevelOfDetail.imageTagAtLevel(image, 0)]
        for l in range(toplevel):
            levels.append(LevelOfDetail.imageTagAtLevel(image, l))
        return LevelOfDetail(levels)

    @staticmethod
    def imageTagAtLevel(image, level):
        if level == 0:
            return str(image.convert("L").quantize(256).resize((1,1)).getpixel((0,0)))
        if level in [1,2,3,4]:
            v = image.convert("L").quantize(256).resize((2,2)).getpixel((level - 1 - 2 * (level // 3), level//3))
            return str(v)
        assert False

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
        logger.info(loc)
        return os.path.exists(loc) and os.path.isdir(loc)

    def store(self, image):
        self.remove()
        path = self.path()
        directory = os.path.dirname(path)
        if len(directory) and not os.path.exists(directory):
            os.makedirs(directory)
        loc = path + ".jpg"
        logger.info("Storing %s", loc)
        image.save(loc)

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
        logger.info("Has branched at level %i", lod.getLevel())
        lod = LevelOfDetail.fromImageAtLevel(image, lod.getLevel() + 1)

    maxSize = config.getint('storage', 'numberOfImages')
    moreImagesAllowed = True

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
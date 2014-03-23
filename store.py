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
import http.client
import base64
import io
import logging
import binascii
import struct
import random
import os.path
import pickle
import hashlib
import datetime
import configparser
import urllib.request
import numpy
import sys

INDEX_FILENAME = "index.pkl"

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

def loadDiskImage():
    with open("original.png", "rb") as img:
        return img.read()


def hashOfFile(filename):
    buffSize = 1024*100
    hasher = hashlib.sha1()
    with open(filename, 'rb') as afile:
        buff = afile.read(buffSize)
        while len(buff) > 0:
            hasher.update(buff)
            buff = afile.read(buffSize)
    return hasher.hexdigest()


class Fingerprint(object):
    FP_MAXIMUM = 256 #Exclusive maximum of fingerprint
    FP_MINIMUM = 0 #Inclusive minimum of fingerprint
    FP_LENGTH = 50*50 #Length/number of dimensions in the fp

    def __init__(self, fp):
        assert isinstance(fp, numpy.ndarray)
        self.fp = fp

    @staticmethod
    def random(rng):
        '''Generate a random fingerprint, given the random number generator'''
        return Fingerprint(numpy.array([rng.randrange(Fingerprint.FP_MINIMUM, Fingerprint.FP_MAXIMUM) for i in range(Fingerprint.FP_LENGTH)]))

    @staticmethod
    def fromImage(image):
        '''Resize, gray and quantize to 10'''
        assert Fingerprint.FP_LENGTH == 50*50
        fp = image.resize((50,50)).convert("L").quantize(Fingerprint.FP_MAXIMUM)
        return Fingerprint(numpy.array(fp.getdata()))

    def asList():
        return self.fp

    @staticmethod
    def fromList(l):
        return Fingerprint(l)

    def distanceTo(self, other):
        return sum(abs(other.fp - self.fp))

    def closest(self, others):
        minDistance = self.distanceTo(others[0])
        minIndex = 0
        for prototypeIndex, prototype in enumerate(others):
            distance = self.distanceTo(prototype)
            if distance < minDistance:
                minIndex = prototypeIndex
        return minIndex


def indexFilename(idx):
    dirIdx = round(idx / 5000)
    return "%i/%i.jpg" % (dirIdx, idx)


def loadIndex():
    index = []
    if os.path.exists(INDEX_FILENAME):
        with open(INDEX_FILENAME, "rb") as indexFile:
            logger.info("Loading index from disk")
            while True:
                try:
                    p = pickle.load(indexFile)
                    index.append(Fingerprint.fromList(p))
                except EOFError as e:
                    return index
    return None

def logStorage(imageTimestamp, closestIndex, filename):
    imageHash = hashOfFile(filename)
    logFilename = "images/storage_%s.log" % imageTimestamp.strftime("%Y-%m-%d")
    with open(logFilename, "a") as storageLog:
        storageLog.write("%s %i %s\n" % (imageTimestamp.strftime("%Y-%m-%dT%H:%M:%S.%f%z"), closestIndex, imageHash))

def loadOrGenerateIndex(size):
    index = loadIndex()
    if index == None:
        index = []
        logger.info("Generating index of %i prototypes" % size)
        rng = random.Random()
        with open(INDEX_FILENAME, "wb") as indexFile:
            for i in range(size):
                fp = Fingerprint.random(rng)
                pickle.dump(fp.fp, indexFile, pickle.HIGHEST_PROTOCOL)
                index.append(fp)
        logger.info("Generated index")
    return index

def storeImageAtIndex(image, index):
    filename = os.path.join("images", indexFilename(index))
    if not os.path.exists(filename):
        #Check if we need to make the directory as well
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    #Store image and log hash and index
    image.save(filename)
    return filename


def loadAndSaveImage(index, config):
    logger.info("Loading image")
    imageData = io.BytesIO(loadCameraImage(config))
    imageTimestamp = datetime.datetime.now()

    image = Image.open(imageData)
    logger.info("Fingerprinting image")
    fp = Fingerprint.fromImage(image)
    logger.info("Finding closest match")
    closestIndex = fp.closest(index)
    logger.info("Storing image")
    filename = storeImageAtIndex(image, closestIndex)
    logStorage(imageTimestamp, closestIndex, filename)

def loadConfig():
    config = configparser.ConfigParser()
    config.read('bucketcam.ini')
    return config

def main():
    config = loadConfig()
    indexSize = config.getint('storage', 'numberOfImages')
    index = loadOrGenerateIndex(indexSize)

    if len(index) != indexSize:
        logger.error("Index loaded has wrong size (remove \"%s\")" % INDEX_FILENAME)
        return 1
    loadAndSaveImage(index, config)
    return 0

if __name__ == "__main__":
    sys.exit(main())
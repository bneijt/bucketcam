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
import store
import logging
import os.path

logging.basicConfig(level = logging.DEBUG, format = '%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

hashCache = {}
HTML_HEAD = '''
<html>
<head><style>
figure {
    max-width: 300px;
    display: inline-block;
    text-align: center;
}
figure.approximateImage {
    background-color: silver;
    color: black;
    font-style: italic
}
img {
    max-width: 100%;
}
</style></head>
<body>
'''
HTML_TAIL='''
</body></html>
'''

def currentHashOf(filename):
    if not filename in hashCache:
        hashCache[filename] = store.hashOfFile(filename)
    return hashCache[filename]

def logFiles():
    for entry in os.listdir("images"):
        if entry.startswith("storage_") and entry.endswith(".log"):
            yield os.path.join("images", entry)
def imageTag(timestamp, filename, exactFile = False):
    return '''
<figure class="%(figureClass)s">
  <img src="%(src)s" alt="Image from %(timestamp)s"/>
  <figcaption>%(timestamp)s</figcaption>
</figure>''' % {
        "src": filename,
        "timestamp": timestamp,
        "figureClass": ("exactImage" if exactFile else "approximateImage")
    }
def main():
    for logFilename in logFiles():
        htmlFilename = os.path.splitext(logFilename)[0] + ".html"
        logger.info("Processing %s -> %s", logFilename, htmlFilename)
        with open(logFilename, 'r') as logFile:
            with open(htmlFilename, 'w') as htmlFile:
                htmlFile.write(HTML_HEAD)
                for line in logFile.readlines():
                    line = line.strip()
                    (timestamp, index, hashWhenStored) = line.split(" ", 2)
                    index = int(index)

                    filename = store.indexFilename(int(index))
                    currentHash = currentHashOf(os.path.join("images", filename))
                    htmlFile.write(imageTag(timestamp, filename, exactFile = hashWhenStored == currentHash))
                htmlFile.write(HTML_TAIL)

if __name__ == "__main__":
    main()
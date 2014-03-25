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
    max-width: 200px;
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
.missingImage {
    -webkit-transform: rotate(-90deg);
    -moz-transform: rotate(-90deg);
    -ms-transform: rotate(-90deg);
    -o-transform: rotate(-90deg);
    transform: rotate(-90deg);

    display: inline-block;
    width: 10px;
    font-size: 80%;
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
def missingTag(time):
    return '''
<div class="missingImage">
%(time)s
</div>''' % {
        "time": time,
    }
def imageTag(time, filename, exactFile = False):
    figureClass = ("exactImage" if exactFile else "approximateImage")
    return '''
<figure class="%(figureClass)s">
    <a href="%(src)s">
        <img src="%(src)s" alt="Image from %(time)s"/>
    </a>
    <figcaption>%(time)s</figcaption>
</figure>''' % {
        "src": filename,
        "time": time,
        "figureClass": figureClass
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
                    (timestamp, hashWhenStored, filename) = line.split(" ", 2)
                    (date, time) = timestamp.split("T", 1)
                    
                    fileStillExists = os.path.exists(filename)
                    if not os.path.exists(filename):
                        htmlFile.write(missingTag(time))
                    else:
                        currentHash = currentHashOf(filename)
                        htmlFile.write(imageTag(time,
                                filename[len("images/"):],
                                exactFile = hashWhenStored == currentHash))
                htmlFile.write(HTML_TAIL)

if __name__ == "__main__":
    main()

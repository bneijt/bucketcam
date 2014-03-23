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
import sys
import logging

logging.basicConfig(level = logging.DEBUG, format = '%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

def main():
    config = store.loadConfig()
    indexSize = config.getint('storage', 'numberOfImages')
    index = store.loadOrGenerateIndex(indexSize)

    if len(index) != indexSize:
        logger.error("Index loaded has wrong size (remove \"%s\")" % INDEX_FILENAME)
        return 1

    while True:
        store.loadAndSaveImage(index, config)

    return 0

if __name__ == "__main__":
    sys.exit(main())

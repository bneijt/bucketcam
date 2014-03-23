Bucketcam
=========
Project goal
------------

    Given a maximum number of images to store,
    store efficiently as possible and keep
    a log of what approximately happened
    in the past.

Status
------
 - Usefullness: way to slow.
 - User friendlyness: works if you can read and write Python code.

Introduction
------------
When calling `./store.py` a single image is downloaded and store in a directory called `images`.
The store script will make sure that there are never more then a configured maximum number of images
stored.
In a log file `images/storage.log` you can review which image was stored under which filename
at which point in time.

Installation
------------
 - Install Python (probably requires version 3 up)
 - Install Pillow (or check if `from PIL import Image` works)

Usage
-----
 - Copy `bucketcam.ini.example` to `bucketcam.ini`
 - Fill in all the configuration parameters with sensible values
 - Run `./store.py` once to create the index
 - Run `./store.py` a second time to download and store an image from the url

Files
-----

 - `store.py`: download and index an image
 - `report.py`: generate an HTML page with images from the log files
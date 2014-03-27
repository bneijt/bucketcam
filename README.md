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
 - Usefullness: experimental but fun
 - User friendlyness: works if you can read and write Python code, no documentation

Introduction
------------
When calling `./store.py` a loop will download images into the `images` directory.
Images are currently loaded in the `loadCameraImage` function, which assumes
you will be downloading an HTTP/HTTPS url with Basic Auth protection.

The url and authentication is configured in `bucketcam.ini`.

In a log file `images/storage.log` you can review which image was stored under which filename
at which point in time. `report.py` can generate an HTML page by parsing the `images/storage.log`
file.

Installation
------------
 - Install Python (developed using 3 up, may work with earlier versions)
 - Install Pillow or PIL (check if `from PIL import Image` works)
 - Copy `bucketcam.ini.example` to `bucketcam.ini` and fill with sensible values

Development
-----------
 - Run `./bootstrap.sh` to install a virtual env or install the
   dependencies mentioned in that file by hand globally on your system.
 - Create patches and send them to me. My personal wishlist includes:
    - Javascript based report.py output with fancy browser an dynamic image loading,
      or some kind of report pagination would also be cool.
    - Configuration parameters to define maximum record speed.
    - Images loaded using two threads and a single value blocking queue.


Usage
-----
 - Run `store.py` next to the `bucketcam.ini` file.

Currently there are no commandline parameters and there is no daemoning behaviour.

Files
-----

 - `store.py`: download and index images in a continuous loop
 - `report.py`: generate an HTML page with images from the log files (next to the log files)

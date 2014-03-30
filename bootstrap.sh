#!/bin/bash
set -e
cd "`dirname "$0"`"
if [ ! -d "virtualenv" ]; then
    virtualenv -p `which python3` virtualenv
fi

. virtualenv/bin/activate
pip install pillow==2.3.1
pip install arrow==0.4.2
pip install flask==0.10.1
echo 'You need virtualenv to work with this'
echo '. virtualenv/bin/activate'


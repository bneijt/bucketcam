#!/bin/bash
set -e
if [ ! -d "virtualenv" ]; then
    virtualenv -p `which python3` virtualenv
fi

. virtualenv/bin/activate
pip install pillow
pip install arrow
echo 'You need virtualenv to work with this'
echo '. virtualenv/bin/activate'


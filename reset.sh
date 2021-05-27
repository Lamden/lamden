#!/usr/bin/env bash
killall lamden python3
git pull
rm -r ~/cilsocks/
if [ -z "$1" ]
then
       cd ../contracting && git pull && python3 setup.py develop && cd ../lamden
else
      cd ../contracting && git pull && $1 setup.py develop && cd ../lamden
fi


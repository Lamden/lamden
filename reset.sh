#!/usr/bin/env bash
killall lamden
git pull
rm -r ~/cilsocks/
cd ../contracting/ && git pull && python3 setup.py develop && cd ../lamden
python3 -m pip install lmdb

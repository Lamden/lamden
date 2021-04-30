#!/usr/bin/env bash
killall lamden
git pull
rm -r ~/cilsocks/
python3 -m pip install lmdb
cd ../contracting/ && git pull && python3 setup.py develop && cd ../lamden


#!/usr/bin/env bash
killall lamden python3
git pull
rm -r ~/cilsocks/
cd ..
rm -R .lamden
cd contracting && git pull && python3 setup.py develop && cd ../lamden
rm -R txs


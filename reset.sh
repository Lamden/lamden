#!/usr/bin/env bash
killall lamden python3
git pull
rm -r ~/cilsocks/
rm -R ~/.lamden
rm -R ~/lamden/txs
cd ../contracting && git pull && python3 setup.py develop && cd ../lamden



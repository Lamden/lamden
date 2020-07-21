#!/usr/bin/env bash
killall lamden
lamden flush all
git pull
rm nohup.out
rm -r ~/cilsocks/
cd ../contracting/ && git pull && python3 setup.py develop && cd ../lamden

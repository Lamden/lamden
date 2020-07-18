#!/usr/bin/env bash
killall lamden
lamden flush all
git pull
rm nohup.out
rm -r ~/cilsocks/
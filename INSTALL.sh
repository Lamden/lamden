#!/usr/bin/env bash
sudo apt-get update
sudo apt-get install python3-pip -y

sudo apt-get install haveged -y
systemctl start haveged
systemctl enable haveged

pip3 install lamden

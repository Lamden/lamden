#!/usr/bin/env bash
sudo apt-get update
sudo apt-get install python3-pip -y
sudo pip3 install --upgrade pip setuptools
sudo apt-get install libgflags-dev libsnappy-dev zlib1g-dev libbz2-dev liblz4-dev libzstd-dev libbz2-dev -y
sudo apt-get install librocksdb-dev -y
sudo apt-get install -y mongodb
sudo apt-get install haveged -y
systemctl start haveged
systemctl enable haveged

git clone https://github.com/Lamden/contracting.git
cd contracting
git fetch
git checkout dev
python3 setup.py develop

cd ~

git clone https://github.com/Lamden/cilantro-enterprise.git
cd cilantro-enterprise
git fetch
git checkout rel-gov-socks
python3 setup.py develop

mongod --dbpath ~/blocks --logpath ~/logs.log --bind_ip_all

pip3 install python-rocksdb

rocks serve &

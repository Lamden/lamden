#!/bin/bash
set -ex

echo "HELLO HELLO HELLO THIS IS NEW CODE"
export PYTHONPATH=$(pwd)

pip3 install -e git://github.com/Lamden/seneca.git@dev#egg=seneca

echo "Waiting for mongo on localhost"
mkdir -p ./data/$HOST_NAME/db/logs
touch ./data/$HOST_NAME/db/logs/log_mongo.log
echo 'Dir created'

mongod --dbpath ./data/db --logpath ./data/db/logs/mongo.log --bind_ip_all &
sleep 1
echo 'started mongod'

python3 ./scripts/create_user.py

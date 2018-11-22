#!/bin/bash
set -ex

export PYTHONPATH=$(pwd)

# echo "Updating seneca..."
# pip3 install seneca --upgrade --no-cache-dir
# echo "Updating vmnet..."
# pip3 install vmnet --upgrade --no-cache-dir

echo "Waiting for mongo on localhost"
mkdir -p ./data/$HOST_NAME/db/logs
touch ./data/$HOST_NAME/db/logs/log_mongo.log
echo 'Dir created'

mongod --dbpath ./data/db --logpath ./data/db/logs/mongo.log --bind_ip_all &
sleep 1
echo 'started mongod'

sudo python3 ./scripts/create_user.py

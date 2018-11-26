#!/bin/bash
set -ex

export PYTHONPATH=$(pwd)

if [ "$CIRCLECI" == "true" ]
then
  export $HOST_NAME="."
fi

# echo "Updating seneca..."
# pip3 install seneca --upgrade --no-cache-dir
# echo "Updating vmnet..."
# pip3 install vmnet --upgrade --no-cache-dir

echo "Waiting for mongo on localhost"
mkdir -p ./data/$HOST_NAME/logs
touch ./data/$HOST_NAME/logs/mongo.log
echo 'Dir created'

python3 ./scripts/create_user.py &
mongod --dbpath ./data/$HOST_NAME --logpath ./data/$HOST_NAME/logs/mongo.log --bind_ip_all

#!/bin/bash
set -ex

source .env

export PYTHONPATH=$(pwd)

echo "Waiting for mongo on localhost"
mkdir -p ./data/$HOST_NAME/logs
touch ./data/$HOST_NAME/logs/mongo.log || true
echo 'Dir created'

python3 ./scripts/create_user.py &
if [[ "$CIRCLECI" == "true" ]]
then
    sudo mongod --dbpath ./data/$HOST_NAME --logpath ./data/$HOST_NAME/logs/mongo.log &
else
    sudo mongod --dbpath ./data/$HOST_NAME --logpath ./data/$HOST_NAME/logs/mongo.log --bind_ip_all &
fi

bash ./scripts/start_redis.sh

#!/bin/bash
set -ex

export PYTHONPATH=$(pwd)

if [ -z "$CIRCLECI" ]
then
  for package in "seneca" "vmnet"
  do
    cp -r ./venv/lib/python3.6/site-packages/$package /usr/local/lib/python3.6/dist-packages
  done
  if [[ "$HOST_NAME" == "" ]]
  then
    export HOST_NAME="."
  fi
fi

echo "Waiting for mongo on localhost"
mkdir -p ./data/$HOST_NAME/logs
touch ./data/$HOST_NAME/logs/mongo.log
echo 'Dir created'

python3 ./scripts/create_user.py &

if [ "$CIRCLECI" == "true" ]
then
  mongod --dbpath ./data/$HOST_NAME --logpath ./data/$HOST_NAME/logs/mongo.log &
else
  mongod --dbpath ./data/$HOST_NAME --logpath ./data/$HOST_NAME/logs/mongo.log --bind_ip_all &
fi

bash ./scripts/start_redis.sh

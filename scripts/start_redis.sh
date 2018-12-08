#!/bin/bash
set -ex

source .env
echo "XXXXX

$VMNET

XXXXX"

if [ -z "$CIRCLECI" ] && [ "$HOST_NAME" != "" ]
then
  for package in "seneca" "vmnet"
  do
    cp -r ./venv/lib/python3.6/site-packages/$package /usr/local/lib/python3.6/dist-packages
  done
fi

# if [[ "$CIRCLECI" == "true" ]]
# then
#     chmod 777 ./venv/bin/activate
#     ./venv/bin/activate
# fi

# Configure env files
export PYTHONPATH=$(pwd)
rm -f ./dump.rdb

echo "Starting Redis server..."

if [ "$HOST_NAME" != "" ] || [ "$VMNET" != "" ]
then
    export REDIS_PORT=$(python3 ./scripts/free_port.py)
    export REDIS_PASSWORD=$(python3 ./scripts/random_password.py)
    mkdir -p docker/$HOST_NAME
    echo "
    REDIS_PORT=$REDIS_PORT
    REDIS_PASSWORD=$REDIS_PASSWORD
    " | sudo tee docker/$HOST_NAME/redis.env
    redis-server docker/redis.conf --port $REDIS_PORT --requirepass $REDIS_PASSWORD
elif [ "$CIRCLECI" == "true" ] || [ "$HOST_NAME" == "" ]
then
    pkill -9 redis-server
    redis-server &
fi

sleep 1
echo "Done."

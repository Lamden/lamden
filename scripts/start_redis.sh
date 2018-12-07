if [ -z "$CIRCLECI" ] && [ "$HOST_NAME" != "" ]
then
  for package in "seneca" "vmnet"
  do
    cp -r ./venv/lib/python3.6/site-packages/$package /usr/local/lib/python3.6/dist-packages
  done
fi

# Find a free port to use
# port=6379
# pw=
port=$(python3 ./scripts/free_port.py)
pw=$(python3 ./scripts/random_password.py)

if [[ "$CIRCLECI" == "true" ]]
then
    chmod 777 ./venv/bin/activate
    ./venv/bin/activate
fi

# Configure env files
export PYTHONPATH=$(pwd)
export REDIS_PORT=$port
export REDIS_PASSWORD=$pw

mkdir -p docker
echo "
REDIS_PORT=$REDIS_PORT
REDIS_PASSWORD=$REDIS_PASSWORD
" | sudo tee docker/redis.env

rm -f ./dump.rdb

echo "Starting Redis server..."
# redis-server
redis-server docker/redis.conf --port $REDIS_PORT --requirepass $REDIS_PASSWORD 2>/dev/null >/dev/null &
#redis-server 2>/dev/null >/dev/null &

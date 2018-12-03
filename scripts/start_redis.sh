if [ -z "$CIRCLECI" ] && [ "$HOST_NAME" != "" ]
then
  for package in "seneca" "vmnet"
  do
    cp -r ./venv/lib/python3.6/site-packages/$package /usr/local/lib/python3.6/dist-packages
  done
fi

# Find a free port to use
port=6397
pw=

# Configure env files
export PYTHONPATH=$(pwd)
export REDIS_PORT=$port
export REDIS_PASSWORD=$pw

echo "
REDIS_PORT=$REDIS_PORT
REDIS_PASSWORD=$REDIS_PASSWORD
" > docker/redis.env

echo "Starting Redis server..."
redis-server

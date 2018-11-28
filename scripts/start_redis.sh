# Find a free port to use
port=$(python3 ./scripts/free_port.py)
pw=$(python3 ./scripts/random_password.py)

# Configure env files
export PYTHONPATH=$(pwd)
export REDIS_PORT=$port
export REDIS_PASSWORD=$pw

echo "
REDIS_PORT=$REDIS_PORT
REDIS_PASSWORD=$REDIS_PASSWORD
" > docker/redis.env

echo "Starting Redis server..."
pkill -9 redis-server
redis-server docker/redis.conf --port $REDIS_PORT --requirepass $REDIS_PASSWORD 2>/dev/null >/dev/null &
redis-server 2>/dev/null >/dev/null &
sleep 1
echo "Done."

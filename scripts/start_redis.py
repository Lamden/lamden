import os
from cilantro.constants.db_config import DATA_DIR


REDIS_CONF = '/etc/redis.conf'
REDIS_DIR = DATA_DIR + '/redis'


def start_redis():
    print("Starting Redis server...")

    if not os.path.exists(REDIS_DIR):
        print("Creating Redis directory at {}".format(REDIS_DIR))
        os.makedirs(REDIS_DIR, exist_ok=True)

    assert os.path.exists(REDIS_CONF), "No redis config file found at path {}".format(REDIS_CONF)

    print("Redis using data directory: {}".format(REDIS_DIR))
    os.system('redis-server /etc/redis.conf')


if __name__ == '__main__':
    start_redis()

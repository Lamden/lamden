import os, sys
from cilantro_ee.db_config import DATA_DIR


REDIS_CONF_PATH = '/etc/redis.conf'
REDIS_DIR = DATA_DIR + '/redis'


def start_redis(conf_path):
    print("Starting Redis server...")
    if not os.path.exists(REDIS_DIR):
        print("Creating Redis directory at {}".format(REDIS_DIR))
        os.makedirs(REDIS_DIR, exist_ok=True)

    print("Redis using data directory: {}".format(REDIS_DIR))

    if conf_path is None:
        print("Starting redis-server with no conf!")
        os.system('redis-server')
    else:
        assert os.path.exists(conf_path), "No redis.conf file found at path {}".format(conf_path)
        print("Starting redis-server with conf file at path {}".format(conf_path))
        os.system('redis-server {}'.format(conf_path))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '-no-conf':
            start_redis(None)
        else:
            start_redis(sys.argv[1])
    else:
        start_redis(REDIS_CONF_PATH)


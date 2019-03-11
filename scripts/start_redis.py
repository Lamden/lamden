import os, sys
from cilantro_ee.constants.db_config import DATA_DIR


LEDIS_CONF_PATH = '/etc/ledis.conf'
LEDIS_DIR = DATA_DIR + '/redis'


def start_redis(conf_path):
    print("Starting Redis server...")
    if not os.path.exists(REDIS_DIR):
        print("Creating Redis directory at {}".format(LEDIS_DIR))
        os.makedirs(REDIS_DIR, exist_ok=True)

    print("Redis using data directory: {}".format(LEDIS_DIR))

    if conf_path is not None:
        assert os.path.exists(conf_path), "No redis.conf file found at path {}".format(conf_path)
        os.system('ledis-server -config={} {}'.format(LEDIS_CONF_PATH, conf_path))
    else:
        os.system('ledis-server')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '-no-conf':
            start_redis(None)
        else:
            start_redis(sys.argv[1])
    else:
        start_redis(LEDIS_CONF_PATH)


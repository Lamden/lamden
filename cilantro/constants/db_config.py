import os


MASTER_DB = 0
DATA_DIR = '/var/db/cilantro_ee'

MONGO_DIR = DATA_DIR + '/mongo'
MONGO_LOG_PATH = MONGO_DIR + '/logs/mongo.log'


def get_redis_port():
    return 6379


def get_redis_password():
    return ''


def config_mongo_dir():
    try:
        os.makedirs(os.path.dirname(MONGO_LOG_PATH), exist_ok=True)
        with open(MONGO_LOG_PATH, 'w+') as f:
            print('Mongo log file created at path {}'.format(MONGO_LOG_PATH))
    except Exception as e:
        print("Error creating mongo log file at path {}. Error -- {}".format(MONGO_LOG_PATH, e))

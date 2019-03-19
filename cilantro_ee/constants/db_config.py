import os


MASTER_DB = 0

DATA_DIR = os.getenv('DATADIR')

if DATA_DIR is None:
    DATA_DIR = '/usr/local/db/cilantro_ee'


MONGO_DIR = DATA_DIR + '/mongo'
MONGO_LOG_PATH = MONGO_DIR + '/logs/mongo.log'


def config_mongo_dir():
    try:
        os.makedirs(os.path.dirname(MONGO_LOG_PATH), exist_ok=True)
        with open(MONGO_LOG_PATH, 'w+') as f:
            print('Mongo log file created at path {}'.format(MONGO_LOG_PATH))
    except Exception as e:
        print("Error creating mongo log file at path {}. Error -- {}".format(MONGO_LOG_PATH, e))

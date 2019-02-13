import os, shutil
from os import getenv as env
from cilantro.constants.db_config import DATA_DIR


def start_mongo():
    host_name = env('HOST_NAME', '')

    mongo_dir = DATA_DIR + '/mongo'
    mongo_log_path = mongo_dir + '/logs/mongo.log'
    try:
        os.makedirs(os.path.dirname(mongo_log_path), exist_ok=True)
        with open(mongo_log_path, 'w+') as f:
            print('Mongo log file created at path {}'.format(mongo_log_path))
    except Exception as e:
        print("Error creating mongo log file at path {}. Error -- {}".format(mongo_log_path, e))

    print('Starting Mongo server...')
    os.system('mongod --dbpath {} --logpath {} --bind_ip_all'.format(mongo_dir, mongo_log_path))


if __name__ == '__main__':
    start_mongo()

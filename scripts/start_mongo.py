import os, shutil, time
from cilantro_ee.constants.db_config import MONGO_DIR, MONGO_LOG_PATH, config_mongo_dir
from cilantro_ee.constants import conf


def start_mongo():
    print("val of conf reset_db: {}".format(conf.RESET_DB))
    if conf.RESET_DB:
        rm_dir = MONGO_DIR + '/'
        print("Removing MongoDB files at directory {}".format(rm_dir))
        shutil.rmtree(MONGO_DIR, ignore_errors=True)
        time.sleep(1)
        print("MongoDB dropped.")

    config_mongo_dir()
    print('Starting Mongo server...')
    os.system('mongod --dbpath {} --logpath {} --bind_ip_all'.format(MONGO_DIR, MONGO_LOG_PATH))


if __name__ == '__main__':
    start_mongo()

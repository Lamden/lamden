#!/usr/bin/env python3.6
import random
import argparse
import string
import os
from pathlib import Path
import configparser
# from free_port import free_port
from cilantro_ee.constants.masternode import *
from cilantro_ee.utils.utils import random_str
import cilantro_ee

if __name__ == '__main__':

    print(Path(os.getcwd()).parent)
    os.environ['PKG_PATH'] = str(Path(os.getcwd()).parent)
    os.environ['CIL_ROOT'] = os.getenv('PKG_PATH') + '/cilantro_ee'
    os.environ['CFG_PATH'] = os.getenv('CIL_ROOT') + '/config'
    os.environ['REDIS_CONF_PATH'] = os.getenv('CFG_PATH') + '/config'

    print(os.environ['PKG_PATH'])
    print(os.environ['CIL_ROOT'])

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--username', default='lamden')
    parser.add_argument('--database', default='mn')
    parser.add_argument('--hostname', default='127.0.0.1')
    parser.add_argument('--output-file', default=cilantro_ee.__path__[0]+'/config/mn_db_conf.ini')
    parser.add_argument('--port', default=27017)
    args = parser.parse_args()

    conf = configparser.RawConfigParser()
    s = 'MN_DB'

    conf.add_section(s)
    conf.set(s, 'username', args.username)
    conf.set(s, 'password', random_str(len=5))
    conf.set(s, 'mn_blk_database', '{}_store'.format(args.database))
    conf.set(s, 'mn_cache_database', '{}_cache'.format(args.database))
    conf.set(s, 'hostname', args.hostname)
    conf.set(s, 'port', args.port)
    conf.set(s, 'replication', REP_FACTOR)
    conf.set(s, 'quorum', QUORUM)
    conf.set(s, 'total_mn', TOTAL_MN)
    conf.set(s, 'mn_id', MN_ID)
    conf.set(s, 'test_hook', TEST_HOOK)
    conf.set(s, 'mn_blk_database', MN_BLK_DATABASE)
    conf.set(s, 'mn_index_database', MN_INDEX_DATABASE)

    with open(args.output_file, 'w') as f:
        conf.write(f)

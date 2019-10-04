"""
Utilities to build sets of signing keys and verifying keys for TestNet
"""
import cilantro_ee
import configparser
from cilantro_ee.core.crypto import wallet
from cilantro_ee.core.logger.base import get_logger
import json, os
from os.path import join

log = get_logger("TestnetNodeBuilder")

DEFAULT_TESTNET_FILE_NAME = '4-4-4.json'
TESTNET_JSON_DIR = os.path.dirname(cilantro_ee.__path__[-1]) + '/constitutions/test'
PUBLIC_JSON_DIR = os.path.dirname(cilantro_ee.__path__[-1]) + '/constitutions/public'
# print("TESTNET JSON DIR: {}".format(TESTNET_JSON_DIR))

TESTNET_KEY = 'testnet'
TESTNET_JSON_KEY = 'testnet_json_file_name'
CONFIG_FILE_NAME = 'testnet.ini'
CONFIG_FILE_PATH = join(TESTNET_JSON_DIR, CONFIG_FILE_NAME)


def set_testnet_config(testnet_json_file='4-4-4.json'):
    config = configparser.ConfigParser()
    config[TESTNET_KEY] = {TESTNET_JSON_KEY: testnet_json_file}

    with open(CONFIG_FILE_PATH, 'w+') as f:
        config.write(f)

    from cilantro_ee.constants.testnet import set_testnet_nodes
    set_testnet_nodes()


def get_testnet_config():
    with open(get_testnet_json_path(), 'r') as f:
        return json.load(f)


def get_config_filename():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)
    return config[TESTNET_KEY][TESTNET_JSON_KEY]


def read_public_constitution(filename) -> dict:
    fpath = PUBLIC_JSON_DIR + '/' + filename
    assert os.path.exists(fpath), "No public constitution file found at path {}".format(fpath)
    with open(fpath) as f:
        return json.load(f)


def get_testnet_json_path():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)
    return join(TESTNET_JSON_DIR, config[TESTNET_KEY][TESTNET_JSON_KEY])


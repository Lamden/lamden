"""
Utilities to build sets of signing keys and verifying keys for TestNet
"""
import cilantro
import configparser
from cilantro.protocol import wallet
from cilantro.logger.base import get_logger
import json, os
from os.path import join

"""
INSTRUCTIONS FOR BUILDING CUSTOM TESTNET CONFIGS

Change NUM_MASTERS/NUM_WITNESSES/NUM_DELEGATES in this file, and run 'make biuld-testnet-json' from the root project directory
A new file called 'new.json' will be added to the testnet_configs directory. Rename this appropriately.
"""
NUM_MASTERS = 4
NUM_WITNESSES = 4
NUM_DELEGATES = 4

log = get_logger("TestnetNodeBuilder")
os.environ['__INHERIT_CONSTITUTION__'] = 'True'

DEFAULT_TESTNET_FILE_NAME = '4-4-4.json'
TESTNET_JSON_DIR = os.path.dirname(cilantro.__path__[-1]) + '/constitutions/test'
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

    from cilantro.constants.testnet import set_testnet_nodes
    set_testnet_nodes()


def get_testnet_config():
    with open(get_testnet_json_path(), 'r') as f:
        return json.load(f)


def get_config_filename():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)
    return config[TESTNET_KEY][TESTNET_JSON_KEY]


def get_testnet_json_path():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)
    return join(TESTNET_JSON_DIR, config[TESTNET_KEY][TESTNET_JSON_KEY])


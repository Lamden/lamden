"""
Utilities to build sets of signing keys and verifying keys for TestNet
"""
import cilantro
import configparser
from cilantro.protocol import wallet
from cilantro.logger.base import get_logger
import json

"""
INSTRUCTIONS FOR BUILDING CUSTOM TESTNET CONFIGS

Change NUM_MASTERS/NUM_WITNESSES/NUM_DELEGATES in this file, and run 'make biuld-testnet-json' from the root project directory
A new file called 'new.json' will be added to the testnet_configs directory. Rename this appropriately.
"""
NUM_MASTERS = 4
NUM_WITNESSES = 4
NUM_DELEGATES = 4

log = get_logger("TestnetNodeBuilder")

DEFAULT_TESTNET_FILE_NAME = '2-2-4.json'
TESTNET_JSON_DIR = cilantro.__path__[0] + '/../testnet_configs/'

TESTNET_KEY = 'testnet'
TESTNET_JSON_KEY = 'testnet_json_file_name'
CONFIG_FILE_NAME = 'testnet.ini'
CONFIG_FILE_PATH = TESTNET_JSON_DIR + CONFIG_FILE_NAME


def set_testnet_config(testnet_json_file='2-2-4.json'):
    config = configparser.ConfigParser()
    config[TESTNET_KEY] = {TESTNET_JSON_KEY: testnet_json_file}

    with open(CONFIG_FILE_PATH, 'w+') as f:
        config.write(f)

    from cilantro.constants.testnet import set_testnet_nodes
    set_testnet_nodes()


def get_testnet_json_path():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)
    return TESTNET_JSON_DIR + config[TESTNET_KEY][TESTNET_JSON_KEY]


def generate_testnet_json(num_masters=NUM_MASTERS, num_witnesses=NUM_WITNESSES, num_delegates=NUM_DELEGATES):
    def _build_nodes(num_nodes=64, prefix='node') -> list:
        nodes = []

        for i in range(num_nodes):
            # name = "{}_{}".format(prefix, i + 1)
            sk, vk = wallet.new()
            nodes.append({'sk': sk, 'vk': vk})

        return nodes

    def build_masternodes(num_nodes=64):
        return _build_nodes(num_nodes=num_nodes, prefix='masternode')

    def build_witnesses(num_nodes=256):
        return _build_nodes(num_nodes=num_nodes, prefix='witness')

    def build_delegate(num_nodes=32):
        return _build_nodes(num_nodes=num_nodes, prefix='delegate')

    testnet = {'masternodes': build_masternodes(num_masters), 'witnesses': build_witnesses(num_witnesses),
               'delegates': build_delegate(num_delegates)}

    with open(TESTNET_JSON_DIR + 'new.json', 'w') as fp:
        json.dump(testnet, fp, indent=4)

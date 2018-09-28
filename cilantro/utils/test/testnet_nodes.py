"""
Utilities to build sets of signing keys and verifying keys for TestNet
"""
import cilantro
from cilantro.protocol import wallet
from cilantro.logger.base import get_logger
import json


log = get_logger("TestnetNodeBuilder")

DEFAULT_TESTNET_FILE_NAME = '2-2-4.json'
TESTNET_JSON_DIR = cilantro.__path__[0] + '/../testnet_configs/'

NUM_MASTERS = 4
NUM_WITNESSES = 4
NUM_DELEGATES = 8


def get_testnet_json_path(file_name=DEFAULT_TESTNET_FILE_NAME):
    return TESTNET_JSON_DIR + file_name


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


def generate_testnet_json(num_masters=NUM_MASTERS, num_witnesses=NUM_WITNESSES, num_delegates=NUM_DELEGATES):
    testnet = {'masternodes': build_masternodes(num_masters), 'witnesses': build_witnesses(num_witnesses),
               'delegates': build_delegate(num_delegates)}

    with open(TESTNET_JSON_DIR + 'new.json', 'w') as fp:
        json.dump(testnet, fp, indent=4)

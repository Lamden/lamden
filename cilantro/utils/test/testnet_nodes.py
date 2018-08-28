"""
Utilities to build sets of signing keys and verifying keys for TestNet
"""
import cilantro
from cilantro.protocol import wallet
from cilantro.logger.base import get_logger
import json


log = get_logger("TestnetNodeBuilder")
TESTNET_JSON_PATH = cilantro.__path__[0] + '/../' + 'testnet.json'

NUM_MASTERS = 64
NUM_WITNESSES = 256
NUM_DELEGATES = 32


def _build_nodes(num_nodes=64, prefix='node') -> dict:
    nodes = {}

    for i in range(num_nodes):
        name = "{}_{}".format(prefix, i + 1)
        sk, vk = wallet.new()
        nodes[name] = {'sk': sk, 'vk': vk}

    return nodes


def build_masternodes(num_nodes=64):
    return _build_nodes(num_nodes=num_nodes, prefix='masternode')


def build_witnesses(num_nodes=256):
    return _build_nodes(num_nodes=num_nodes, prefix='witness')


def build_delegate(num_nodes=32):
    return _build_nodes(num_nodes=num_nodes, prefix='delegate')


def generate_testnet_json(num_masters=NUM_MASTERS, num_witnesses=NUM_WITNESSES, num_delegates=NUM_DELEGATES):
    testnet = {'masters': build_masternodes(num_masters), 'witnesses': build_masternodes(num_witnesses),
               'delegates': build_masternodes(num_delegates)}

    with open(TESTNET_JSON_PATH, 'w') as fp:
        json.dump(testnet, fp, indent=4)

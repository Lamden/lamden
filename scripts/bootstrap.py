from cilantro_ee.utils.factory import MASTERNODE, DELEGATE, start_node
from cilantro_ee.constants import conf
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.logger.base import overwrite_logger_level
from contracting.logger import overwrite_logger_level as sen_overwrite_log
import os, sys, time

from cilantro_ee.utils.test.testnet_config import read_public_constitution
from contracting.client import ContractingClient
from cilantro_ee.contracts import sync
from cilantro_ee.protocol import wallet
import requests


def boot(delay):

    # Initialize database
    client = ContractingClient()

    if conf.RESET_DB:
        client.raw_driver.flush()

    v = VKBook()

    # Pull VKBook smart contract out to verify it has been set properl
    vk_book_contract = client.get_contract('vkbook')

    # Pull masternode and delegate VKs from state
    masternodes = vk_book_contract.get_masternodes()
    delegates = vk_book_contract.get_delegates()

    # Set them to in-memory system wide constants
    VKBook.set_masternodes(masternodes)
    VKBook.set_delegates(delegates)

    # Get the node's ip address
    print("Configuring your node...")
    conf.HOST_IP = requests.get('https://api.ipify.org').text

    # Determine what type the node is based on VK
    sk = bytes.fromhex(conf.SK)
    _, vk = wallet.new(seed=sk)

    node_type = None
    if vk in masternodes:
        node_type = MASTERNODE
    elif vk in delegates:
        node_type = DELEGATE

    if node_type is None:
        raise Exception("You are not in the network!")

    print("Bootstrapping node with start delay of {}...".format(delay))
    time.sleep(delay)

    overwrite_logger_level(conf.LOG_LEVEL)

    start_node(signing_key=conf.SK, node_type=node_type)

if __name__ == '__main__':
    _delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    boot(_delay)

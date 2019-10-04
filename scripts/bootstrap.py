from contracting.client import ContractingClient
from cilantro_ee.constants import conf

client = ContractingClient()

if conf.RESET_DB:
    client.raw_driver.flush()

from cilantro_ee.utils.factory import MASTERNODE, DELEGATE, start_node
from cilantro_ee.services.storage.vkbook import PhoneBook
from cilantro_ee.core.logger.base import overwrite_logger_level
import sys, time
from cilantro_ee.core.crypto import wallet
import requests

def boot(delay):
    # Determine what type the node is based on VK
    sk = bytes.fromhex(conf.SK)
    _, vk = wallet.new(seed=sk)

    node_type = None
    if vk in PhoneBook.masternodes:
        node_type = MASTERNODE
    elif vk in PhoneBook.delegates:
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

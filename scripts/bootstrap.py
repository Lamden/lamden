from contracting.client import ContractingClient
from cilantro_ee.constants import conf
from cilantro_ee.contracts.sync import seed_vkbook



if conf.RESET_DB:
    ContractingClient().raw_driver.flush()

seed_vkbook(conf.CONSTITUTION_FILE)

from cilantro_ee.utils.factory import MASTERNODE, DELEGATE, start_node
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.core.logger.base import overwrite_logger_level
import sys, time
from cilantro_ee.core.crypto import wallet
import requests

def boot(delay):
    # Determine what type the node is based on VK
    sk = bytes.fromhex(conf.SK)
    _, vk = wallet.new(seed=sk)

    phone_book = VKBook()

    node_type = None
    if vk in phone_book.masternodes:
        node_type = MASTERNODE
    elif vk in phone_book.delegates:
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

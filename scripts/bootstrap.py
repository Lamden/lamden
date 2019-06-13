from cilantro_ee.utils.factory import MASTERNODE, DELEGATE, start_node
from cilantro_ee.constants import conf
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.logger.base import overwrite_logger_level
import sys, time
from contracting.client import ContractingClient
from cilantro_ee.protocol import wallet
import requests


def boot(delay):

    with open(conf.CIL_CONF_PATH, 'r') as f:
        print(f.read())

    # Initialize database
    client = ContractingClient()

    if conf.RESET_DB:
        client.raw_driver.flush()

    v = VKBook()

    conf.HOST_IP = requests.get('https://api.ipify.org').text

    # Determine what type the node is based on VK
    sk = bytes.fromhex(conf.SK)
    _, vk = wallet.new(seed=sk)

    print('Metering enabled: {}'.format(conf.STAMPS_ENABLED))

    node_type = None
    if vk in v.get_masternodes():
        node_type = MASTERNODE
    elif vk in v.get_delegates():
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

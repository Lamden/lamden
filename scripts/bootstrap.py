from contracting.client import ContractingClient
from cilantro_ee.constants import conf

client = ContractingClient()

if conf.RESET_DB:
    client.raw_driver.flush()

from cilantro_ee.utils.factory import MASTERNODE, DELEGATE, start_node
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.logger.base import overwrite_logger_level
import sys, time
from cilantro_ee.protocol import wallet
import requests
from cilantro_ee.utils.test.testnet_config import read_public_constitution

def boot(delay):
    # Initialize database




    # Determine what type the node is based on VK
    sk = bytes.fromhex(conf.SK)
    _, vk = wallet.new(seed=sk)

    print('Metering enabled: {}'.format(conf.STAMPS_ENABLED))
    print("{}".format(conf.RESET_DB))
    print("{}".format(conf.CONSTITUTION_FILE))
    print("{}".format(conf.SSL_ENABLED))
    print("{}".format(conf.NONCE_ENABLED))
    print("{}".format(conf.STAMPS_ENABLED))
    print("{}".format(conf.LOG_LEVEL))
    print("{}".format(conf.SEN_LOG_LEVEL))
    print("{}".format(conf.SK))
    print("{}".format(conf.BOOT_MASTERNODE_IP_LIST))
    print("{}".format(conf.BOOT_DELEGATE_IP_LIST))
    print("{}".format(conf.BOOTNODES))
    print('contents of constitution: {}'.format(read_public_constitution(conf.CONSTITUTION_FILE)))

    node_type = None
    if vk in PhoneBook.masternodes:
        node_type = MASTERNODE
    elif vk in PhoneBook.delegates:
        node_type = DELEGATE

    if node_type is None:
        raise Exception("You are not in the network!")

    print(PhoneBook.masternodes)
    print(PhoneBook.delegates)

    print("Bootstrapping node with start delay of {}...".format(delay))
    time.sleep(delay)

    overwrite_logger_level(conf.LOG_LEVEL)

    start_node(signing_key=conf.SK, node_type=node_type)


if __name__ == '__main__':
    _delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    boot(_delay)

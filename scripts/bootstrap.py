from cilantro_ee.utils.factory import MASTERNODE, DELEGATE, start_node
from cilantro_ee.constants.conf import CilantroConf, CIL_CONF_PATH
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
    assert os.path.exists(CIL_CONF_PATH), "No config file found at path {}. Comon man get it together!".format(CIL_CONF_PATH)

    client = ContractingClient()

    if CilantroConf.RESET_DB:
        client.raw_driver.flush()

    print("Seeding genesis contract and building VKBook...")

    book = read_public_constitution(CilantroConf.CONSTITUTION_FILE)
    mns = [node['vk'] for node in book['masternodes']]
    dels = [node['vk'] for node in book['delegates']]

    sync.submit_contract_with_construction_args('vkbook', args={'masternodes': mns, 'delegates': dels})

    vk_book_contract = client.get_contract('vkbook')

    masternodes = vk_book_contract.get_masternodes()
    delegates = vk_book_contract.get_delegates()

    VKBook.set_masternodes(masternodes)
    VKBook.set_delegates(delegates)

    print("Configuring your node...")
    CilantroConf.HOST_IP = requests.get('https://api.ipify.org').text
    print("Your public IP is: {}".format(CilantroConf.HOST_IP))
    sk = bytes.fromhex(CilantroConf.SK)
    _, vk = wallet.new(seed=sk)
    print("Your VK is: {}.".format(vk))

    # Determine what type the node is based on VK
    node_type = None
    if vk in mns:
        node_type = MASTERNODE
    elif vk in dels:
        node_type = DELEGATE

    if node_type is None:
        raise Exception("You are not in the network!")

    print("Bootstrapping node with start delay of {}...".format(delay))
    time.sleep(delay)

    overwrite_logger_level(CilantroConf.LOG_LEVEL)

    start_node(signing_key=CilantroConf.SK, node_type=node_type)

if __name__ == '__main__':
    _delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    boot(_delay)

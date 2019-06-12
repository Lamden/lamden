from cilantro_ee.utils.factory import NodeFactory
from cilantro_ee.constants.conf import CilantroConf, CIL_CONF_PATH
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.logger.base import overwrite_logger_level
from contracting.logger import overwrite_logger_level as sen_overwrite_log
import os, sys, time

from cilantro_ee.utils.test.testnet_config import read_public_constitution
from contracting.client import ContractingClient
from cilantro_ee.contracts import sync


def boot(delay):
    assert os.path.exists(CIL_CONF_PATH), "No config file found at path {}. Comon man get it together!".format(CIL_CONF_PATH)

    #
    # TODO: RESET THE DBS. THEY ALREADY ARE SEEDED AND NOT RESEEDING SO THE OLD VKS FOR DELEGATES ARE STILL IN THERE AND BLOWING UP BLOCKMANAGER
    #
    print("Seeding genesis contract and building VKBook...")

    book = read_public_constitution(CilantroConf.CONSTITUTION_FILE)
    mns = [node['vk'] for node in book['masternodes']]
    dels = [node['vk'] for node in book['delegates']]

    sync.submit_contract_with_construction_args('vkbook', args={'masternodes': mns,
                                                                'delegates': dels})
    client = ContractingClient()
    vk_book_contract = client.get_contract('vkbook')

    masternodes = vk_book_contract.get_masternodes()
    delegates = vk_book_contract.get_delegates()

    VKBook.set_masternodes(masternodes)
    VKBook.set_delegates(delegates)

    print(delegates)
    print(VKBook.get_delegates())

    print("Bootstrapping node with start delay of {}...".format(delay))
    time.sleep(delay)

    # print("VKBook mns {}".format(VKBook.get_masternodes()))
    overwrite_logger_level(CilantroConf.LOG_LEVEL)

    if CilantroConf.NODE_TYPE == 'witness':
        NodeFactory.run_witness(signing_key=CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'delegate':
        sen_overwrite_log(CilantroConf.SEN_LOG_LEVEL)
        NodeFactory.run_delegate(CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'masternode':
        NodeFactory.run_masternode(CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'scheduler':
        NodeFactory.run_scheduler(CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'notifier':
        while True:
            print("I am a notifier but i has no logic yet :(")
            time.sleep(1)
        pass

    else:
        raise Exception("Unrecognized node type {}".format(CilantroConf.NODE_TYPE))


if __name__ == '__main__':
    _delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    boot(_delay)

from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')
from cilantro.constants.testnet import *
from cilantro.constants.test_suites import CI_FACTOR

from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test, CILANTRO_PATH
from cilantro.utils.test.mp_testables import MPNodeBase
from cilantro.storage.vkbook import VKBook
import unittest, time


class TestNodeBootStage(MPTestCase):
    config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-6.json'.format(CILANTRO_PATH)
    # log_lvl = 19

    @vmnet_test
    def test_boot_6(self):
        """
        Tests creating a network with 2 Masternodes, 2 Witnesses, and 4 Delegates. Ensures everyone can connect to
        each other.
        """
        def assert_boot(test_obj):
            pass
            # from cilantro.storage.vkbook import VKBook
            # mns, dels, wits, = set(VKBook.get_masternodes()), set(VKBook.get_delegates()), set(VKBook.get_witnesses())
            # assert test_obj.online_mns == mns, "Missing mns: {}".format(mns - test_obj.online_mns)
            # assert test_obj.online_wits == wits, "Missing wits: {}".format(wits - test_obj.online_wits)
            # assert test_obj.online_dels == dels, "Missing dels: {}".format(dels - test_obj.online_dels)

        BLOCK = False

        self.log.important("on host machine:")
        VKBook.test_print_nodes()

        mn_0 = MPNodeBase(sk=TESTNET_MASTERNODES[0]['sk'], name='[node_1]MN_0', config_fn=None, assert_fn=assert_boot, block_until_rdy=BLOCK)
        mn_1 = MPNodeBase(sk=TESTNET_MASTERNODES[1]['sk'], name='[node_2]MN_1', config_fn=None, assert_fn=assert_boot, block_until_rdy=BLOCK)
        wit_0 = MPNodeBase(sk=TESTNET_WITNESSES[0]['sk'], name='[node_3]WITNESS_0', config_fn=None, assert_fn=assert_boot, block_until_rdy=BLOCK)
        wit_1 = MPNodeBase(sk=TESTNET_WITNESSES[1]['sk'], name='[node_4]WITNESS_1', config_fn=None, assert_fn=assert_boot, block_until_rdy=BLOCK)
        del_0 = MPNodeBase(sk=TESTNET_DELEGATES[0]['sk'], name='[node_5]DELEGATE_0', config_fn=None, assert_fn=assert_boot, block_until_rdy=BLOCK)
        del_1 = MPNodeBase(sk=TESTNET_DELEGATES[1]['sk'], name='[node_5]DELEGATE_1', config_fn=None, assert_fn=assert_boot, block_until_rdy=BLOCK)

        all_nodes = (mn_0, mn_1, wit_0, wit_1, del_0, del_1)
        all_vks = (TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[1]['vk'], TESTNET_WITNESSES[0]['vk'],
                   TESTNET_WITNESSES[1]['vk'], TESTNET_DELEGATES[0]['vk'], TESTNET_DELEGATES[1]['vk'],)

        self.start(timeout=CI_FACTOR*60)


if __name__ == '__main__':
    # Hello CI, want to go for a run?
    unittest.main()

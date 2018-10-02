# ------------------------------------------------------------------------
# Mock out get_testnet_json_path to return the desired Testnet config json
JSON_FILE_NAME = '2-2-4.json'

import cilantro
from unittest.mock import patch
patched_json_dir = cilantro.__path__[0] + '/../testnet_configs/' + JSON_FILE_NAME
with patch('cilantro.utils.test.testnet_nodes.get_testnet_json_path') as mock_path:
    mock_path.return_value = patched_json_dir
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
# Done mocking
# ------------------------------------------------------------------------
from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test, CILANTRO_PATH
from cilantro.utils.test.mp_testables import MPPubSubAuth
from cilantro.storage.db import VKBook
import unittest, time


def config_sub(test_obj):
    from unittest.mock import MagicMock
    test_obj.handle_sub = MagicMock()
    return test_obj


class TestLargeNetwork(MPTestCase):
    config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-8.json'.format(CILANTRO_PATH)

    @vmnet_test(run_webui=True)
    def test_2_4_4(self):
        """
        Tests creating a network with 2 Masternodes, 4 Witnesses, and 4 Delegates. Ensures everyone can connect to
        each other.
        """
        def assert_sub(test_obj):
            c_args = test_obj.handle_sub.call_args_list
            assert len(c_args) == 7, "Expected 7 messages (one from each node). Instead, got:\n{}".format(c_args)

        BLOCK = False

        mn_0 = MPPubSubAuth(sk=TESTNET_MASTERNODES[0]['sk'], name='[node_1]MN_0', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        mn_1 = MPPubSubAuth(sk=TESTNET_MASTERNODES[1]['sk'], name='[node_2]MN_1', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)

        wit_0 = MPPubSubAuth(sk=TESTNET_WITNESSES[0]['sk'], name='[node_3]WITNESS_0', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        wit_1 = MPPubSubAuth(sk=TESTNET_WITNESSES[1]['sk'], name='[node_4]WITNESS_1', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)

        del_0 = MPPubSubAuth(sk=TESTNET_DELEGATES[0]['sk'], name='[node_5]DELEGATE_0', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        del_1 = MPPubSubAuth(sk=TESTNET_DELEGATES[1]['sk'], name='[node_6]DELEGATE_1', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        del_2 = MPPubSubAuth(sk=TESTNET_DELEGATES[2]['sk'], name='[node_7]DELEGATE_2', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        del_3 = MPPubSubAuth(sk=TESTNET_DELEGATES[3]['sk'], name='[node_8]DELEGATE_3', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)

        time.sleep(16)  # Nap while nodes hookup

        all_nodes = (mn_0, mn_1, wit_0, wit_1, del_0, del_1, del_2, del_3)
        all_vks = (TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[1]['vk'], TESTNET_WITNESSES[0]['vk'],
                   TESTNET_WITNESSES[1]['vk'], TESTNET_DELEGATES[0]['vk'], TESTNET_DELEGATES[1]['vk'],
                   TESTNET_DELEGATES[2]['vk'], TESTNET_DELEGATES[3]['vk'],)

        # Each node PUBS on its own IP
        for n in all_nodes:
            n.add_pub_socket(ip=n.ip, secure=True)

        # Each node SUBs to everyone else (except themselves)
        for i, n in enumerate(all_nodes):
            n.add_sub_socket(secure=True)
            node_vk = all_vks[i]
            for vk in VKBook.get_all():
                if vk == node_vk: continue
                n.connect_sub(vk=vk)

        time.sleep(8)  # Allow time for VK lookups

        # Make each node pub a msg
        for n in all_nodes:
            n.send_pub("hi from {} with ip {}".format(n.name, n.ip).encode())

        self.start(timeout=16)


if __name__ == '__main__':
    unittest.main()

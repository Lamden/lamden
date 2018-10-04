# ------------------------------------------------------------------------
# Mock out get_testnet_json_path to return the desired Testnet config json
JSON_NAME = '4-4-8.json'

import cilantro
from unittest.mock import patch
FAKE_JSON_DIR = cilantro.__path__[0] + '/../testnet_configs/' + JSON_NAME
with patch('cilantro.utils.test.testnet_nodes.get_testnet_json_path') as mock_path:
    mock_path.return_value = FAKE_JSON_DIR
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


class TestThiccNetwork(MPTestCase):
    config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-16.json'.format(CILANTRO_PATH)

    @vmnet_test(run_webui=True)
    def test_4_4_8(self):
        """
        Tests creating a network with 2 Masternodes, 4 Witnesses, and 4 Delegates. Ensures everyone can connect to
        each other.
        """
        def assert_sub(test_obj):
            c_args = test_obj.handle_sub.call_args_list
            assert len(c_args) == 15, "Expected 15 messages (one from each node). Instead, got:\n{}".format(c_args)

        all_keys = TESTNET_MASTERNODES + TESTNET_WITNESSES + TESTNET_DELEGATES
        nodes = []

        for i, key_pair in enumerate(all_keys):
            node = MPPubSubAuth(sk=key_pair['sk'], name='NODE_{}'.format(i + 1), config_fn=config_sub,
                                assert_fn=assert_sub, block_until_rdy=False)
            node._vk = key_pair['vk']
            nodes.append(node)

        time.sleep(20)  # Nap while nodes hookup

        # Each node PUBS on its own IP
        for n in nodes:
            n.add_pub_socket(ip=n.ip, secure=True)

        # Each node SUBs to everyone else (except themselves)
        for n in nodes:
            n.add_sub_socket(secure=True)
            for vk in VKBook.get_all():
                if vk == n._vk: continue
                n.connect_sub(vk=vk)

        time.sleep(8)  # Allow time for VK lookups

        # Make each node pub a msg
        for n in nodes:
            n.send_pub("hi from {} with ip {}, and vk {}".format(n.name, n.ip, n._vk).encode())

        self.start(timeout=16)


if __name__ == '__main__':
    unittest.main()

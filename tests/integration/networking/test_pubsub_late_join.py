from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')
from cilantro.constants.testnet import *
from cilantro.constants.test_suites import CI_FACTOR

from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test, CILANTRO_PATH
from cilantro.utils.test.mp_testables import MPPubSubAuth
from cilantro.storage.vkbook import VKBook
import unittest, time


def config_sub(test_obj):
    from unittest.mock import MagicMock
    test_obj.handle_sub = MagicMock()
    return test_obj


class TestLateJoining(MPTestCase):
    config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-6.json'.format(CILANTRO_PATH)
    # log_lvl = 19

    def config_node(self, node: MPPubSubAuth, sub_list: list):
        self.log.test("Configuring node named {}".format(node.name))
        node.add_pub_socket(ip=node.ip, secure=True)
        node.add_sub_socket(secure=True)
        for vk in sub_list:
            node.connect_sub(vk=vk)

    @vmnet_test(run_webui=True)  # TODO turn of web UI
    def test_2_2_2(self):
        """
        Tests creating a network with 2 Masternodes, 2 Witnesses, and 4 Delegates. Ensures everyone can connect to
        each other.
        """
        def assert_sub(test_obj):
            c_args = test_obj.handle_sub.call_args_list
            assert len(c_args) == 5, "Expected 5 messages (one from each node). Instead, got:\n{}".format(c_args)

        BLOCK = False

        self.log.test("Spinning up first 3 nodes")
        node1 = MPPubSubAuth(sk=TESTNET_MASTERNODES[0]['sk'], name='[node_1]MN_0', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        node2 = MPPubSubAuth(sk=TESTNET_MASTERNODES[1]['sk'], name='[node_2]MN_1', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        node3 = MPPubSubAuth(sk=TESTNET_WITNESSES[0]['sk'], name='[node_3]WITNESS_0', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)

        time.sleep(12*CI_FACTOR)  # Nap while nodes hookup

        all_vks = [TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[1]['vk'], TESTNET_WITNESSES[0]['vk'],
                   TESTNET_WITNESSES[1]['vk'], TESTNET_DELEGATES[0]['vk'], TESTNET_DELEGATES[1]['vk']]

        for n in (node1, node2, node3):
            self.config_node(n, all_vks)

        time.sleep(10*CI_FACTOR)  # Nap while nodes try to add sockets

        # Spin up last 2 nodes
        node4 = MPPubSubAuth(sk=TESTNET_WITNESSES[1]['sk'], name='[node_4]WITNESS_1', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        node5 = MPPubSubAuth(sk=TESTNET_DELEGATES[0]['sk'], name='[node_5]DELEGATE_0', config_fn=config_sub, assert_fn=assert_sub, block_until_rdy=BLOCK)
        time.sleep(12*CI_FACTOR)  # Nap while nodes hookup

        self.log.test("Spinning up remaining 2 nodes")
        for n in (node4, node5):
            self.config_node(n, all_vks)

        time.sleep(20*CI_FACTOR)  # Nap while the remaining nodes connect

        # Everyone pubs
        self.log.test("Sending PUB messages from all nodes")
        for n in (node1, node2, node3, node4, node5):
            n.send_pub("hi from {} with ip {}".format(n.name, n.ip).encode())

        self.start(timeout=30)


if __name__ == '__main__':
    # Hello CI, want to go for a run?
    unittest.main()

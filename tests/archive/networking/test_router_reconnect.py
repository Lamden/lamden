from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')
from cilantro.constants.testnet import *
from cilantro.constants.test_suites import CI_FACTOR

from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test, CILANTRO_PATH
from cilantro.utils.test.mp_testables import MPRouterAuth
from cilantro.messages.signals.poke import Poke
import unittest, time


def config_node(test_obj):
    from unittest.mock import MagicMock
    test_obj.handle_router_msg = MagicMock()
    return test_obj


class TestRouterReconnect(MPTestCase):
    config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-6.json'.format(CILANTRO_PATH)
    # log_lvl = 19

    def config_node(self, node: MPRouterAuth, vk_list: list):
        self.log.test("Configuring node named {}".format(node.name))
        node.create_router_socket(identity=node.ip.encode(), secure=True)
        node.bind_router_socket(ip=node.ip)
        for vk in vk_list:
            if node.vk == vk: continue
            node.connect_router_socket(vk=vk)

    @vmnet_test(run_webui=False)  # TODO turn of web UI
    def test_late_joining_router(self):
        def assert_router(test_obj):
            c_args = test_obj.handle_router_msg.call_args_list
            assert len(c_args) == 4, "Expected 4 messages (one from each node). Instead, got:\n{}".format(c_args)

        BLOCK = False
        DOWN_TIME = 30

        self.log.test("Spinning up first 3 nodes")
        node1 = MPRouterAuth(sk=TESTNET_MASTERNODES[0]['sk'], name='node_1', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node2 = MPRouterAuth(sk=TESTNET_MASTERNODES[1]['sk'], name='node_2', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node3 = MPRouterAuth(sk=TESTNET_WITNESSES[0]['sk'], name='node_3', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)

        time.sleep(8*CI_FACTOR)  # Nap while nodes hookup

        all_vks = [TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[1]['vk'], TESTNET_WITNESSES[0]['vk'],
                   TESTNET_WITNESSES[1]['vk'], TESTNET_DELEGATES[0]['vk']]

        self.log.test("Configuring nodes 1, 2, and 3")
        for n in (node1, node2, node3):
            self.config_node(n, all_vks)

        time.sleep(DOWN_TIME*CI_FACTOR)  # Nap while nodes try to add sockets

        # Spin up last 2 nodes
        self.log.test("Spinning up remaining 2 nodes")
        node4 = MPRouterAuth(sk=TESTNET_WITNESSES[1]['sk'], name='node_4', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node5 = MPRouterAuth(sk=TESTNET_DELEGATES[0]['sk'], name='node_5', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)

        time.sleep(16*CI_FACTOR)  # Nap while nodes hookup

        self.log.test("Configuring nodes 4 and 5")
        for n in (node4, node5):
            self.config_node(n, all_vks)

        time.sleep(15*CI_FACTOR)  # Nap while the remaining nodes connect

        # Everyone sends messages to everyone
        self.log.test("Sending messages from all nodes")
        for sender in (node1, node2, node3, node4, node5):
            for receiver in (node1, node2, node3, node4, node5):
                if sender == receiver: continue
                sender.send_msg(Poke.create(), receiver.ip.encode())

        self.start(timeout=20)

    @vmnet_test(run_webui=False)  # TODO turn of web UI
    def test_join_then_drop_then_reconnect(self):
        def assert_router(test_obj):
            c_args = test_obj.handle_router_msg.call_args_list
            assert len(c_args) == 4, "Expected 4 messages (one from each node). Instead, got:\n{}".format(c_args)

        BLOCK = False
        DOWN_TIME = 30

        self.log.test("Spinning up all 5 nodes...")
        node1 = MPRouterAuth(sk=TESTNET_MASTERNODES[0]['sk'], name='node_1', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node2 = MPRouterAuth(sk=TESTNET_MASTERNODES[1]['sk'], name='node_2', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node3 = MPRouterAuth(sk=TESTNET_WITNESSES[0]['sk'], name='node_3', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node4 = MPRouterAuth(sk=TESTNET_WITNESSES[1]['sk'], name='node_4', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node5 = MPRouterAuth(sk=TESTNET_DELEGATES[0]['sk'], name='node_5', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)

        time.sleep(8*CI_FACTOR)  # Nap while nodes hookup

        all_vks = [TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[1]['vk'], TESTNET_WITNESSES[0]['vk'],
                   TESTNET_WITNESSES[1]['vk'], TESTNET_DELEGATES[0]['vk']]
        all_nodes = (node1, node2, node3, node4, node5)

        self.log.test("Connecting all nodes to each other")
        for n in all_nodes:
            self.config_node(n, all_vks)

        time.sleep(8*CI_FACTOR)  # Allow time for nodes to finish lookups

        for n in all_nodes[-2:]:
            self.log.test("\n\nKilling node named {}\n".format(n.container_name))
            self.kill_node(n.container_name)

        self.log.test("\n"+"-"*32 + "\nWaiting {} seconds before bringing nodes back up\n".format(DOWN_TIME) + "-"*32)
        time.sleep(DOWN_TIME)

        for n in all_nodes[-2:]:
            self.log.test("Reviving node named {}".format(n.container_name))
            self.start_node(n.container_name)
            self.rerun_node_script(n.container_name)
            n.reconnect()  # Reconnects the host machine's socket to the remote container

        # Allow time for revived nodes to bootstrap
        time.sleep(10*CI_FACTOR)

        # Reconnect the 2 revived nodes
        self.log.test("Reconnecting last 2 nodes to all others")
        for n in all_nodes[-2:]:
            self.config_node(n, all_vks)

        # Allow time for revived nodes to finish lookups
        time.sleep(16*CI_FACTOR)  # damn why does this take so long :( ... 10 will not work

        # Everyone sends messages to everyone
        self.log.test("Sending messages from all nodes")
        for sender in (node1, node2, node3, node4, node5):
            for receiver in (node1, node2, node3, node4, node5):
                if sender == receiver: continue
                sender.send_msg(Poke.create(), receiver.ip.encode())

        self.start(timeout=20)

    @vmnet_test(run_webui=False)  # TODO turn of web UI
    def test_join_then_drop_then_send_msg_before_reconnect(self):
        def assert_router(test_obj):
            c_args = test_obj.handle_router_msg.call_args_list
            assert len(c_args) == 4, "Expected 4 messages (one from each node). Instead, got:\n{}".format(c_args)

        BLOCK = False
        DOWN_TIME = 30

        self.log.test("Spinning up all 5 nodes...")
        node1 = MPRouterAuth(sk=TESTNET_MASTERNODES[0]['sk'], name='node_1', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node2 = MPRouterAuth(sk=TESTNET_MASTERNODES[1]['sk'], name='node_2', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node3 = MPRouterAuth(sk=TESTNET_WITNESSES[0]['sk'], name='node_3', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node4 = MPRouterAuth(sk=TESTNET_WITNESSES[1]['sk'], name='node_4', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)
        node5 = MPRouterAuth(sk=TESTNET_DELEGATES[0]['sk'], name='node_5', config_fn=config_node, assert_fn=assert_router, block_until_rdy=BLOCK)

        time.sleep(8*CI_FACTOR)  # Nap while nodes hookup

        all_vks = [TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[1]['vk'], TESTNET_WITNESSES[0]['vk'],
                   TESTNET_WITNESSES[1]['vk'], TESTNET_DELEGATES[0]['vk']]
        all_nodes = (node1, node2, node3, node4, node5)

        self.log.test("Connecting all nodes to each other")
        for n in all_nodes:
            self.config_node(n, all_vks)

        time.sleep(8*CI_FACTOR)  # Allow time for nodes to finish lookups

        for n in all_nodes[-2:]:
            self.log.test("\n\nKilling node named {}\n".format(n.container_name))
            self.kill_node(n.container_name)

        self.log.test("\n"+"-"*32 + "\nWaiting {} seconds before bringing nodes back up\n".format(DOWN_TIME) + "-"*32)
        time.sleep(DOWN_TIME)

        for n in all_nodes[-2:]:
            self.log.test("Reviving node named {}".format(n.container_name))
            self.start_node(n.container_name)
            self.rerun_node_script(n.container_name)
            n.reconnect()  # Reconnects the host machine's socket to the remote container

        # Allow time for revived nodes to bootstrap
        time.sleep(10*CI_FACTOR)

        # Reconnect the 2 revived nodes
        self.log.test("Reconnecting last 2 nodes to all others")
        for n in all_nodes[-2:]:
            self.config_node(n, all_vks)

        # Allow time for revived nodes to finish lookups
        time.sleep(16*CI_FACTOR)  # damn why does this take so long :( ... 10 will not work

        # Everyone sends messages to everyone
        self.log.test("Sending messages from all nodes")
        for sender in (node1, node2, node3, node4, node5):
            for receiver in (node1, node2, node3, node4, node5):
                if sender == receiver: continue
                sender.send_msg(Poke.create(), receiver.ip.encode())

        self.start(timeout=20)


if __name__ == '__main__':
    # Hello CI, want to go for a run?
    unittest.main()

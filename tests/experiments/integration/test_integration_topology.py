# import unittest
# from cilantro_ee.utils.test import MPMasternode, MPTestCase, vmnet_test
# from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
# from unittest.mock import call
# from cilantro_ee.utils.test.god import *
# from cilantro_ee.nodes.masternode.masternode import *
# import time
# from cilantro_ee.protocol.wallet import Wallet
#
# """
# Here we do integration tests on our network topology. We spin up nodes on the VM, and ensure that they can talk
# to each other how we expect them to.
# """
#
# W = Wallet
# sk1, vk1 = W.new()
# sk2, vk2 = W.new()
# sk3, vk3 = W.new()
# sk4, vk4 = W.new()
# FILTERS = ['FILTER_' + str(i) for i in range(100)]
# URLS = ['tcp://127.0.0.1:' + str(i) for i in range(9000, 9999, 10)]
#
# log = get_logger("TopologyIntegrationTest")
#
#
# class TopologyIntegrationTest(MPTestCase):
#
#     @vmnet_test
#     def test_masternode_receives_std_tx(self):
#         """
#         Tests that a Masternode properly receives a standard TXs from clients via its POST endpoint
#         """
#         def config_mn(mn: Masternode):
#             assert mn.state == MNRunState, "y tho..current state is {}".format(mn.state)
#
#             run_state = mn.states[MNRunState]
#             run_state.handle_tx = MagicMock()
#
#             return mn
#
#         def assert_mn(mn: Masternode):
#             run_state = mn.states[MNRunState]
#             run_state.handle_tx.assert_has_calls([call(tx1), call(tx2)], any_order=True)
#
#         mn_sk = TESTNET_MASTERNODES[0]['sk']
#
#         # TODO change these to contract transactions
#         tx1 = God.create_currency_tx(FALCON, DAVIS, 210)
#         tx2 = God.create_currency_tx(STU, FALCON, 150)
#
#         masternode = MPMasternode(name='Masternode', config_fn=config_mn, assert_fn=assert_mn, sk=mn_sk)
#         from cilantro_ee.utils.test import MPComposer
#         # comp = MPComposer(sk=mn_sk)
#
#         time.sleep(0.25)  # give masternode a quick sec to get his web server ready
#
#         God.send_tx(tx1)
#         God.send_tx(tx2)
#
#         log.critical("STARTING TEST")
#         self.start()
#
#     # def test_masternode_witness_pubsub(self):
#     #     """
#     #     Tests that a Masternode publishes transactions to the TESTNET_WITNESSES
#     #     """
#     #     pass
#
#
# if __name__ == '__main__':
#     unittest.main()

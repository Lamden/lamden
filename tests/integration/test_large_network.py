# from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test, CILANTRO_PATH
# from cilantro.utils.test.mp_testables import MPPubSubAuth
# from cilantro.storage.db import VKBook
# from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
# import unittest, time
#
#
# """
# !!! NOTE  !!!
# these tests require a 2 MN / 2 WITNESS / 4 DELEGATE config in testnet.json
#
# In the future, we need to develop a way to swap out testnet.json depending on what integration test we are running
# """
#
# def config_sub(test_obj):
#     from unittest.mock import MagicMock
#     test_obj.handle_sub = MagicMock()
#     return test_obj
#
#
# class TestLargeNetwork(MPTestCase):
#     config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-8.json'.format(CILANTRO_PATH)
#
#     @vmnet_test(run_webui=True)
#     def test_2_4_4(self):
#         """
#         Tests creating a network with 2 Masternodes, 4 Witnesses, and 4 Delegates. Ensures everyone can connect to
#         each other.
#         """
#         def assert_sub(test_obj):
#             c_args = test_obj.handle_sub.call_args_list
#             assert len(c_args) == 7, "Expected 7 messages (one from each node). Instead, got {}".format(c_args)
#
#         mn_0 = MPPubSubAuth(sk=TESTNET_MASTERNODES[0]['sk'], name='MN_0', config_fn=config_sub, assert_fn=assert_sub)
#         mn_1 = MPPubSubAuth(sk=TESTNET_MASTERNODES[1]['sk'], name='MN_1', config_fn=config_sub, assert_fn=assert_sub)
#
#         wit_0 = MPPubSubAuth(sk=TESTNET_WITNESSES[0]['sk'], name='WITNESS_0', config_fn=config_sub, assert_fn=assert_sub)
#         wit_1 = MPPubSubAuth(sk=TESTNET_WITNESSES[1]['sk'], name='WITNESS_1', config_fn=config_sub, assert_fn=assert_sub)
#
#         del_0 = MPPubSubAuth(sk=TESTNET_DELEGATES[0]['sk'], name='DELEGATE_0', config_fn=config_sub, assert_fn=assert_sub)
#         del_1 = MPPubSubAuth(sk=TESTNET_DELEGATES[1]['sk'], name='DELEGATE_1', config_fn=config_sub, assert_fn=assert_sub)
#         del_2 = MPPubSubAuth(sk=TESTNET_DELEGATES[2]['sk'], name='DELEGATE_2', config_fn=config_sub, assert_fn=assert_sub)
#         del_3 = MPPubSubAuth(sk=TESTNET_DELEGATES[3]['sk'], name='DELEGATE_3', config_fn=config_sub, assert_fn=assert_sub)
#
#         time.sleep(10)  # Nap while nodes hookup
#
#         all_nodes = (mn_0, mn_1, wit_0, wit_1, del_0, del_1, del_2, del_3)
#         all_vks = (TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[1]['vk'], TESTNET_WITNESSES[0]['vk'],
#                    TESTNET_WITNESSES[1]['vk'], TESTNET_DELEGATES[0]['vk'], TESTNET_DELEGATES[1]['vk'],
#                    TESTNET_DELEGATES[2]['vk'], TESTNET_DELEGATES[3]['vk'],)
#
#         # Each node PUBS on its own IP
#         for n in all_nodes:
#             n.add_pub_socket(ip=n.ip, secure=True)
#
#         # Each node SUBs to everyone else (except themselves)
#         for i, n in enumerate(all_nodes):
#             n.add_sub_socket(secure=True)
#             node_vk = all_vks[i]
#             for vk in VKBook.get_all():
#                 if vk == node_vk: continue
#                 n.connect_sub(vk=vk)
#
#         time.sleep(8)  # Allow time for VK lookups
#
#         # Make each node pub a msg
#         for n in all_nodes:
#             n.send_pub("hi from {} with ip {}".format(n.name, n.ip).encode())
#
#         self.start(timeout=16)
#
#
# if __name__ == '__main__':
#     unittest.main()

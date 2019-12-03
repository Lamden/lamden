# from cilantro_ee.nodes.masternode.nonce import NonceManager
# from unittest import TestCase
#
#
# class TestNonce(TestCase):
#
#     def test_create_nonce(self):
#         user_vk = 'ABCD' * 16
#         nonce = NonceManager.create_nonce(user_vk)
#
#         self.assertTrue(user_vk in nonce)
#         self.assertEqual(len(nonce), 64*2 + 1)
#         self.assertTrue(NonceManager.check_if_exists(nonce))
#
#     def test_create_delete(self):
#         user_vk = 'ABCD' * 16
#         nonce = NonceManager.create_nonce(user_vk)
#
#         self.assertTrue(NonceManager.check_if_exists(nonce))
#         NonceManager.delete_nonce(nonce)
#         self.assertFalse(NonceManager.check_if_exists(nonce))
#

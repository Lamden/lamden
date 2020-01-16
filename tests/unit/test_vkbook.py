from unittest import TestCase
from cilantro_ee.storage.vkbook import VKBook
from contracting.client import ContractingClient
from cilantro_ee.contracts import sync


class TestVKBook(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()

    def tearDown(self):
        self.client.flush()

    def test_submit_new_vkbook(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        sync.submit_vkbook({
            'masternodes': masternodes,
            'delegates': delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': stamps,
            'enable_nonces': nonces
        }, overwrite=True)

        v = VKBook()

        self.assertEqual(v.masternodes, masternodes)
        self.assertEqual(v.delegates, delegates)


    def test_reinitialization_does_not_resubmit_and_overwrite(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        sync.submit_vkbook({
            'masternodes': masternodes,
            'delegates': delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': stamps,
            'enable_nonces': nonces
        }, overwrite=True)

        v = VKBook()

        new_masternodes = ['d', 'e', 'f']
        new_delegates = ['a', 'b', 'c']
        new_stamps = True
        new_nonces = True

        sync.submit_vkbook({
            'masternodes': new_masternodes,
            'delegates': new_delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': new_stamps,
            'enable_nonces': new_nonces
        }, overwrite=False)

        v = VKBook()

        self.assertEqual(v.masternodes, masternodes)
        self.assertEqual(v.delegates, delegates)

    def test_state_sync_returns_masternodes_and_delegates(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        sync.submit_vkbook({
            'masternodes': masternodes,
            'delegates': delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': stamps,
            'enable_nonces': nonces
        }, overwrite=False)

        v = VKBook()

        self.assertEqual(v.core_nodes, masternodes + delegates)

    def test_all_returns_masternodes_delegates_and_witnesses(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        sync.submit_vkbook({
            'masternodes': masternodes,
            'delegates': delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': stamps,
            'enable_nonces': nonces
        }, overwrite=False)

        v = VKBook()

        self.assertEqual(v.core_nodes, masternodes + delegates + [])

    def test_check_master(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']

        stamps = False
        nonces = False

        mn = 'a'

        sync.submit_vkbook({
            'masternodes': masternodes,
            'delegates': delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': stamps,
            'enable_nonces': nonces
        }, overwrite=False)

        v = VKBook()
        self.assertEqual(v.masternodes[0], mn)

    def test_check_delegate(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']

        stamps = False
        nonces = False

        dl = 'd'

        sync.submit_vkbook({
            'masternodes': masternodes,
            'delegates': delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': stamps,
            'enable_nonces': nonces
        }, overwrite=False)

        v = VKBook()
        self.assertEqual(v.delegates[0], dl)

    def test_vkbook(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        sync.submit_vkbook({
            'masternodes': masternodes,
            'delegates': delegates,
            'masternode_min_quorum': 1,
            'enable_stamps': stamps,
            'enable_nonces': nonces
        }, overwrite=False)

        v = VKBook()

        self.assertEqual(1, v.masternode_quorum_min)
        self.assertEqual(v.masternodes, masternodes)




from unittest import TestCase
from cilantro_ee.services.storage.vkbook import VKBook
from contracting.client import ContractingClient


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

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)

        self.assertEqual(v.masternodes, masternodes)
        self.assertEqual(v.delegates, delegates)
        self.assertEqual(v.stamps_enabled, stamps)
        self.assertEqual(v.nonces_enabled, nonces)

    def test_reinitialization_does_not_resubmit_and_overwrite(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)

        new_masternodes = ['d', 'e', 'f']
        new_delegates = ['a', 'b', 'c']
        new_stamps = True
        new_nonces = True

        v = VKBook(new_masternodes, new_delegates, stamps=new_stamps, nonces=new_nonces, debug=False)

        self.assertEqual(v.masternodes, masternodes)
        self.assertEqual(v.delegates, delegates)
        self.assertEqual(v.stamps_enabled, stamps)
        self.assertEqual(v.nonces_enabled, nonces)

    def test_witnesses_as_default(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)

        self.assertEqual(v.witnesses, [])

    def test_notifiers_as_default(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)

        self.assertEqual(v.notifiers, [])

    def test_schedulers_as_default(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)

        self.assertEqual(v.schedulers, [])

    def test_state_sync_returns_masternodes_and_delegates(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)

        self.assertEqual(v.state_sync, masternodes + delegates)

    def test_all_returns_masternodes_delegates_and_witnesses(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)

        self.assertEqual(v.all, masternodes + delegates + [])

    def test_check_master(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']

        stamps = False
        nonces = False

        mn = 'a'

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)
        self.assertEqual(v.masternodes[0], mn)

    def test_check_delegate(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']

        stamps = False
        nonces = False

        dl = 'd'

        v = VKBook(masternodes, delegates, stamps = stamps, nonces = nonces, debug = False)
        self.assertEqual(v.delegates[0], dl)

    def test_vkbook(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces)

        self.assertEqual(1, v.masternode_quorum_min)
        self.assertEqual(v.masternodes, masternodes)


    def test_phonebook(self):
        self.assertEqual(2, PhoneBook.masternode_quorum_min)
        self.assertNotEqual(PhoneBook.masternodes, None)




from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from lamden.contracts import sync
from pathlib import Path
from unittest import TestCase

class TestMembers(TestCase):
    def setUp(self):
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver)
        self.client.flush()

        with open(sync.DEFAULT_PATH + '/genesis/currency.s.py') as f:
            self.client.submit(f.read(), 'currency', constructor_args={'vk': 'test'})
        with open(sync.DEFAULT_PATH + '/genesis/foundation.s.py') as f:
            self.client.submit(f.read(), 'foundation', constructor_args={'vk': 'test'})

        self.foundation = self.client.get_contract('foundation')
        self.currency = self.client.get_contract('currency')

    def test_withdraw(self):
        # Send money to foundation
        self.currency.transfer(signer='test', amount=10000, to='foundation')

        self.foundation.withdraw(amount=5000, signer='test')

        self.assertEqual(self.currency.balances['test'], 288_090_567-5000)

    def test_change_owner(self):
        self.currency.transfer(signer='test', amount=10000, to='foundation')

        self.foundation.change_owner(vk='xxx', signer='test')

        with self.assertRaises(AssertionError):
            self.foundation.withdraw(amount=123, signer='test')

        self.foundation.withdraw(amount=123, signer='xxx')
        self.assertEqual(self.currency.balances['xxx'], 123)

    def test_change_owner_fails_if_not_owner(self):
        with self.assertRaises(AssertionError):
            self.foundation.change_owner(vk='xxx', signer='yyy')
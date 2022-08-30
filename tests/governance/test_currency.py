from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from lamden.contracts import sync
from pathlib import Path
from unittest import TestCase

class TestCurrency(TestCase):
    def setUp(self):
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver)
        self.client.flush()

        with open(sync.DEFAULT_PATH + '/genesis/currency.s.py') as f:
            self.client.submit(f.read(), name='currency', constructor_args={'vk': 'test'})

        self.currency = self.client.get_contract('currency')

    def tearDown(self):
        self.client.flush()

    def test_seed_sets_founder_balance(self):
        self.assertEqual(288_090_567, self.contract_driver.get('currency.balances:test'))

    def test_transfer_raises_if_negative_balance(self):
        with self.assertRaises(AssertionError):
            self.currency.transfer(amount=-69, to='nikita')

    def test_transfer_raises_if_not_enough_coins(self):
        with self.assertRaises(AssertionError):
            self.currency.transfer(amount=69, to='nikita')

    def test_transfer_updates_balances_correctly(self):
        self.currency.transfer(signer='test', amount=69, to='nikita')

        self.assertEqual(69, self.contract_driver.get('currency.balances:nikita'))
        self.assertEqual(288_090_567 - 69, self.contract_driver.get('currency.balances:test'))

    def test_balance_of_nonexisting_returns_0(self):
        self.assertEqual(0, self.currency.balance_of(account='nikita'))

    def test_balance_of_returns_correct_balance(self):
        self.assertEqual(288_090_567, self.currency.balance_of(account='test'))

    def test_allowance_returns_zero_if_no_allowance(self):
        self.assertEqual(0, self.currency.allowance(owner='test', spender='nikita'))

    def test_allowance_returns_correct_amount(self):
        self.currency.approve(signer='test', amount=69, to='nikita')

        self.assertEqual(69, self.currency.allowance(owner='test', spender='nikita'))

    def test_approve_raises_if_sending_negative_balance(self):
        with self.assertRaises(AssertionError):
            self.currency.approve(signer='test', amount=-69, to='nikita')

    def test_approve_returns_and_updates_balances_correctly(self):
        self.assertEqual(69, self.currency.approve(signer='test', amount=69, to='nikita'))
        self.assertEqual(69, self.contract_driver.get('currency.balances:test:nikita'))

    def test_transfer_from_raises_if_sending_negative_balance(self):
        with self.assertRaises(AssertionError):
            self.currency.transfer_from(amount=-69, to='nikita', main_account='test')

    def test_transfer_from_raises_if_not_enough_coins_approved_to_send(self):
        with self.assertRaises(AssertionError):
            self.currency.transfer_from(amount=69, to='nikita', main_account='test')

    def test_transfer_from_raises_if_not_enough_coins_to_send(self):
        self.currency.approve(signer='jeff', amount=69, to='nikita')

        with self.assertRaises(AssertionError):
            self.currency.transfer_from(signer='nikita', amount=69, to='nikita', main_account='jeff')

    def test_transfer_from_updates_balances_correctly(self):
        self.currency.approve(signer='test', amount=69, to='nikita')

        self.currency.transfer_from(signer='nikita', amount=69, to='nikita', main_account='test')

        self.assertEqual(0, self.contract_driver.get('currency.balances:test:nikita'))
        self.assertEqual(288_090_567 - 69, self.contract_driver.get('currency.balances:test'))
        self.assertEqual(69, self.contract_driver.get('currency.balances:nikita'))

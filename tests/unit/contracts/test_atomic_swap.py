import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.unit.contracts.smart_contract_testcase import *
import seneca.libs.types as std
from seneca.execute import execute_contract

log = get_logger("Testelection")

class TestAtomicSwap(SmartContractTestCase):
    @contract(
        'atomic_swap',
        'currency',
        ('DAVIS', 'atomic_swap'),
        ('TJ', 'atomic_swap'),
    )
    def test_initatiate_transfer(self, atomic_swap, currency, davis, carl):
        tau_address = atomic_swap.find_address('tau')
        hash = std.sha256('some_secret')
        davis.initiate_transfer('TJ', hash, 696947, tau_address)
        self.assertTrue(davis.is_reserved('DAVIS', 696947, hash))

    @contract(
        'atomic_swap',
        'currency',
        ('DAVIS', 'atomic_swap')
    )
    def test_initiate_fail_exists(self, atomic_swap, currency, davis):
        tau_address = atomic_swap.find_address('tau')
        hash = std.sha256('some_secret')
        davis.initiate_transfer('TJ', hash, 696947, tau_address)
        with self.assertRaises(Exception) as context:
            davis.initiate_transfer('TJ', hash, 696947, tau_address)

    @contract(
        'atomic_swap',
        'currency',
        ('DAVIS', 'atomic_swap'),
        ('TJ', 'atomic_swap'),
    )
    def test_redeem_transfer(self, atomic_swap, currency, davis, carl):
        tau_address = atomic_swap.find_address('tau')
        hash = std.sha256('some_secret')
        davis.initiate_transfer('TJ', hash, 696947, tau_address)
        carl.redeem_transfer('some_secret')
        self.assertFalse(carl.is_reserved('DAVIS', 696947, hash))

    @contract(
        'atomic_swap',
        'currency',
        ('DAVIS', 'atomic_swap'),
        ('TJ', 'atomic_swap'),
    )
    def test_redeem_transfer_non_tau(self, atomic_swap, currency, davis, carl):
        eth_address = atomic_swap.find_address('eth')
        hash = std.sha256('some_secret')
        davis.initiate_transfer('TJ', hash, 696947, eth_address)
        carl.redeem_transfer('some_secret')
        self.assertTrue(carl.is_reserved('TJ', 696947, hash))

    @contract(
        'atomic_swap',
        'currency',
        ('DAVIS', 'atomic_swap'),
        ('TJ', 'atomic_swap'),
    )
    def test_redeem_transfer_no_previous_agreement(self, atomic_swap, currency, davis, carl):
        tau_address = atomic_swap.find_address('tau')
        hash = std.sha256('some_secret')
        with self.assertRaises(Exception) as context:
            carl.redeem_transfer('some_secret')

    @contract(
        'atomic_swap',
        'currency',
        ('DAVIS', 'atomic_swap'),
        ('TJ', 'atomic_swap'),
    )
    def test_refund_transfer(self, atomic_swap, currency, davis, carl):
        tau_address = atomic_swap.find_address('tau')
        hash = std.sha256('some_secret')
        davis.initiate_transfer('TJ', hash, 696947, tau_address)
        davis.refund_transfer(hash, 'TJ')
        self.assertFalse(carl.is_reserved('DAVIS', 696947, hash))

    @contract(
        'atomic_swap',
        'currency',
        ('DAVIS', 'atomic_swap'),
        ('TJ', 'atomic_swap'),
    )
    def test_refund_transfer_non_tau(self, atomic_swap, currency, davis, carl):
        eth_address = atomic_swap.find_address('eth')
        hash = std.sha256('some_secret')
        davis.initiate_transfer('TJ', hash, 696947, eth_address)
        davis.refund_transfer(hash, 'TJ')
        self.assertTrue(davis.is_reserved('TJ', 696947, hash))


if __name__ == '__main__':
    unittest.main()

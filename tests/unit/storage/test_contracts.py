from unittest import TestCase
import unittest
from unittest import mock
from cilantro_ee.storage.contracts import *
from seneca.engine.interface import SenecaInterface
from cilantro_ee.protocol import wallet


TEST_WALLET1 = wallet.new()
TEST_WALLET2 = wallet.new()


class TestContracts(TestCase):

    def setUp(self):
        with SenecaInterface() as interface:
            interface.r.flushdb()

    def test_seed_contracts_get_code_str(self):
        seed_contracts()
        with SenecaInterface(concurrent_mode=False) as interface:
            self.assertTrue(bool(interface.get_code_obj('currency')))
            self.assertTrue(bool(interface.get_code_obj('sample')))

            expected_snipped = 'UNITTEST_FLAG_CURRENCY_SENECA 1729'
            actual_code = interface.get_code_str('currency')
            self.assertTrue(expected_snipped in actual_code)

    def test_seed_contracts_author_info(self):
        seed_contracts()
        with SenecaInterface(concurrent_mode=False) as interface:
            contract_metadata = interface.get_contract_meta('currency')
            actual_author = contract_metadata['author']

            self.assertEqual(actual_author, GENESIS_AUTHOR)

    def test_seed_contracts_doesnt_screw_imports_after(self):
        seed_contracts()

        # We should be able to import stuff normally now
        import cilantro_ee
        from collections import OrderedDict
        from cilantro_ee.logger.base import get_logger
        import capnp
        # import envelope_capnp

    @mock.patch('cilantro_ee.storage.contracts.SHOULD_MINT_WALLET', True)
    @mock.patch('cilantro_ee.storage.contracts.MINT_AMOUNT', 6967)
    @mock.patch('cilantro_ee.storage.contracts.ALL_WALLETS', [TEST_WALLET1, TEST_WALLET2])
    def test_seed_contracts_mints_wallets(self):
        seed_contracts()

        with SenecaInterface(concurrent_mode=False) as interface:
            for wallet in [TEST_WALLET1, TEST_WALLET2]:
                sk, vk = wallet
                output = interface.execute_function('seneca.contracts.currency.balance_of', sender=GENESIS_AUTHOR,
                                                     stamps=1000, wallet_id=vk)
                # print('got output {} for vk {}'.format(output, vk))
                self.assertEqual(output['output'], 6967)



if __name__ == '__main__':
    unittest.main()

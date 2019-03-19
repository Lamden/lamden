from unittest import TestCase
import unittest
from unittest import mock
from cilantro_ee.storage.contracts import *
from cilantro_ee.storage.ledis import SafeLedis
from cilantro_ee.protocol import wallet
from seneca.engine.interpreter.executor import Executor


TEST_WALLET1 = wallet.new()
TEST_WALLET2 = wallet.new()


class TestContracts(TestCase):

    def setUp(self):
        SafeLedis.flushdb()

    def test_seed_contracts_doesnt_screw_imports_after(self):
        mint_wallets()

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
        mint_wallets()
        interface = Executor(metering=False, concurrency=False)
        for wallet in [TEST_WALLET1, TEST_WALLET2]:
            sk, vk = wallet
            balances = interface.get_resource('currency', 'balances')
            # print('got output {} for vk {}'.format(output, vk))
            self.assertEqual(balances[vk], 6967)


if __name__ == '__main__':
    unittest.main()

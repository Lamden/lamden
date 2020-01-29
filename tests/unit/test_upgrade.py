from unittest import TestCase
from cilantro_ee.contracts import sync
from cilantro_ee.storage.vkbook import VKBook
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient


class TestUpgrade(TestCase):
    # def setup(self):
    #     masternodes = ['a', 'b', 'c']
    #     delegates = ['d', 'e', 'f']
    #     stamps = False
    #     nonces = False
    #
    #     v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)
    #     self.assertIsNotNone(v)

    # check initial state of Upgrade
    def test_init_state(self):
        driver = ContractDriver()
        driver.flush()

        sync.sync_genesis_contracts()

        upg = driver.get_contract_keys('upgrade')
        print('done')

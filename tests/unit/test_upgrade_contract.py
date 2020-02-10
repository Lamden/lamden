import unittest

from cilantro_ee.contracts import sync
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
import cilantro_ee

class TestUpgradeContract(unittest.TestCase):
    def test_upd_sync(self):
        client = ContractingClient()
        client.flush()

        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')

        self.assertIsNotNone('upgrade')


if __name__ == '__main__':
    unittest.main()

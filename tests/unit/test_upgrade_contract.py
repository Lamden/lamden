import unittest

from cilantro_ee.contracts import sync
from contracting.db.driver import ContractDriver


class TestUpgradeContract(unittest.TestCase):
    def test_upd_sync(self):
        driver = ContractDriver()
        driver.flush()

        sync.sync_genesis_contracts()
        self.assertIsNotNone('upgrade')


if __name__ == '__main__':
    unittest.main()

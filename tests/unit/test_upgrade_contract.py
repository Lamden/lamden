import unittest
from cilantro_ee.contracts import sync
from cilantro_ee.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
import cilantro_ee


class TestUpgradeContract(unittest.TestCase):
    def setUp(self):

        self.client = ContractingClient()

        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')
        sync.submit_node_election_contracts(
            initial_masternodes=['stu', 'raghu', 'steve'],
            boot_mns=2,
            initial_delegates=['tejas', 'alex'],
            boot_dels=3,
        )

    def tearDown(self):
        self.client.flush()

    # test if upgrade contract sync's as genesis contract
    def test_upd_sync(self):
        upgrade = self.client.get_contract('upgrade')
        self.assertIsNotNone(upgrade)

    def test_init_state(self):
        state = self.client.get_contract('upgrade')
        lock = state.quick_read(variable='upg_lock')
        consensus = state.quick_read(variable='upg_consensus')

        self.assertEqual(lock, False)
        self.assertEqual(consensus, False)

    def test_vote(self):
        pass

    def test_ready(self):
        pass


if __name__ == '__main__':
    unittest.main()

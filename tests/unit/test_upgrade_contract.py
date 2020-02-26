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
        upgrade = self.client.get_contract('upgrade')
        lock = upgrade.quick_read(variable='upg_lock')
        consensus = upgrade.quick_read(variable='upg_consensus')

        self.assertEqual(lock, False)
        self.assertEqual(consensus, False)

    def test_consensys_n_reset(self):
        upgrade = self.client.get_contract('upgrade')

        upgrade.quick_write('tot_mn', 3)
        upgrade.quick_write('tot_dl', 3)
        upgrade.quick_write('mn_vote', 1)
        upgrade.quick_write('dl_vote', 2)

        upgrade.run_private_function(
            f='vote',
            vk=1
        )

        result = upgrade.quick_read(variable='upg_consensus')

        self.assertEqual(result, True)

        upgrade.run_private_function(
            f='reset_contract',
        )

        result = upgrade.quick_read(variable='upg_consensus')
        self.assertEqual(result, False)


if __name__ == '__main__':
    unittest.main()

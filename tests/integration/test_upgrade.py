from lamden.crypto.wallet import Wallet
from lamden.upgrade import build_pepper2
from pathlib import Path
from tests.integration.mock.mock_data_structures import MockBlocks
from tests.integration.mock.threaded_node import create_a_node, ThreadedNode
from tests.unit.helpers.mock_transactions import get_new_currency_tx
from unittest import TestCase
import asyncio
import json
import shutil

class TestUpgrade(TestCase):
    def setUp(self):
        self.founder_wallet, self.node_wallet = [Wallet(), Wallet()]
        self.blocks = MockBlocks(
            num_of_blocks=1,
            founder_wallet=self.founder_wallet,
            initial_members={
                'masternodes': [
                    self.node_wallet.verifying_key
                ]
            }
        )
        self.genesis_block = self.blocks.get_block_by_index(index=0)

        self.threaded_nodes = []

        self.temp_storage_root = Path().cwd().joinpath('temp_network')
        if self.temp_storage_root.is_dir():
            shutil.rmtree(self.temp_storage_root)

    def tearDown(self):
        for tn in self.threaded_nodes:
            self.await_async_process(tn.stop)
        #if self.temp_storage_root.is_dir():
        #    shutil.rmtree(self.temp_storage_root)

    def create_node(self, index=0):
        tn = create_a_node(
            node_wallet=self.node_wallet,
            genesis_block=self.genesis_block,
            index=index,
            temp_storage_root=self.temp_storage_root
        )
        self.threaded_nodes.append(tn)

        return tn

    def start_node(self, tn: ThreadedNode):
        tn.start()

        while not tn.node or not tn.node.started or not tn.node.network.running:
            self.await_async_process(asyncio.sleep, 1)

    def create_and_start_node(self, index=0) -> ThreadedNode:
        tn = self.create_node(index=index)
        self.start_node(tn)

        return tn

    def await_async_process(self, process, *args, **kwargs):
        tasks = asyncio.gather(
            process(*args, **kwargs)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def await_node_reaches_height(self, tn: ThreadedNode, height):
        while tn.blocks.total_blocks() != height:
            self.await_async_process(asyncio.sleep, 0.1)

    def test_upgrade(self):
        tn = self.create_and_start_node()
        tn.set_smart_contract_value(f'upgrade.upgrade_state:consensus', value=True)
        tn.set_smart_contract_value(f'upgrade.upgrade_state:lamden_branch_name', value='dev-upgrade')
        tn.set_smart_contract_value(f'upgrade.upgrade_state:contracting_branch_name', value='dev-staging')
        tn.set_smart_contract_value(f'upgrade.upgrade_state:pepper', value=build_pepper2())

        tx_args = {
            'to': Wallet().verifying_key,
            'wallet': Wallet(),
            'amount': 10,
            'processor': tn.wallet.verifying_key
        }
        tn.send_tx(json.dumps(get_new_currency_tx(**tx_args)).encode())

        self.await_node_reaches_height(tn, 2)
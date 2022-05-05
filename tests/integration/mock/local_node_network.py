import asyncio
import time

from tests.integration.mock.threaded_node import ThreadedNode
from lamden.crypto.wallet import Wallet
from lamden.storage import BlockStorage

from contracting.db.driver import ContractDriver, FSDriver

from pathlib import Path
import shutil

import unittest
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from typing import List

class LocalNodeNetwork:
    def __init__(self, constitution: dict={}, bootnodes: list = [], num_of_masternodes: int = 0, num_of_delegates: int = 0):
        self.masternodes = []
        self.delegates = []

        self.constitution = dict(constitution)
        self.bootnodes = dict(bootnodes)

        self.current_path = Path.cwd()
        self.temp_network_dir = Path(f'{self.current_path}/temp_network')

        try:
            shutil.rmtree(self.temp_network_dir)
        except FileNotFoundError:
            pass

        self.temp_network_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.loop = asyncio.get_event_loop()

            if self.loop.is_closed():
                self.loop = None
        except:
            self.loop = None
        finally:
            if not self.loop:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

        self.create_new_network(
            num_of_delegates=num_of_delegates,
            num_of_masternodes=num_of_masternodes
        )

    @property
    def all_nodes(self) -> List[ThreadedNode]:
        return self.masternodes + self.delegates

    @property
    def num_of_nodes(self) -> int:
        return len(self.all_nodes)

    @property
    def all_nodes_started(self) -> bool:
        nodes_started = [tn.node.started for tn in self.all_nodes]
        return all(n == True for n in nodes_started)

    def create_new_network(self, num_of_masternodes: int = 0, num_of_delegates: int = 0):
        if num_of_masternodes + num_of_delegates == 0:
            return

        masternode_wallets = [("masternode", Wallet(), m) for m in range(num_of_masternodes)]
        delegate_wallets = [("delegate", Wallet(), d + len(masternode_wallets)) for d in range(num_of_delegates)]
        node_wallets = masternode_wallets + delegate_wallets

        self.constitution = self.create_constitution(
            node_wallets=node_wallets
        )

        for node_info in node_wallets:
            self.bootnodes[node_info[1].verifying_key] = f'tcp://127.0.0.1:{19000 + node_info[2]}'

        for node_info in node_wallets:
            tn = self.create_node(
                node_type=node_info[0],
                node_wallet=node_info[1],
                index=node_info[2]
            )
            tn.start()
            while not tn.node_started:
                self.loop.run_until_complete(asyncio.sleep(0.1))

        while not self.all_nodes_started:
            print("NETWORK ASYNC SLEEPING TO WAIT")
            self.loop.run_until_complete(asyncio.sleep(1))

        print('done')


    def create_constitution(self, node_wallets: list = []):
        return {
            'masternodes': [m[1].verifying_key for m in node_wallets if m[0] == "masternode"],
            'delegates': [d[1].verifying_key for d in node_wallets if d[0] == "delegate"],
        }

    def create_node(self, node_type, index: int = None, node_wallet: Wallet = Wallet(), node: ThreadedNode = None):
        assert node_type in ['masternode', 'delegate'], "node_type must be 'masternode' or 'delegate'"

        node_dir = Path(f'{self.temp_network_dir}/{node_wallet.verifying_key}')
        node_state_dir = Path(f'{node_dir}/state')

        node_state_dir.mkdir(parents=True, exist_ok=True)

        driver = ContractDriver(driver=FSDriver(root=Path(node_state_dir)))
        block_storage = BlockStorage(home=Path(node_dir))

        if not node:
            node = ThreadedNode(
                index=index or self.num_of_nodes,
                node_type=node_type,
                wallet=node_wallet,
                constitution=self.constitution,
                bootnodes=self.bootnodes,
                driver=driver,
                block_storage=block_storage
            )

        if node.node_type == 'masternode':
            self.masternodes.append(node)

        if node.node_type == 'delegate':
            self.delegates.append(node)

        return node

    def run_threaded_node(self, node):
        node.start()

        while not node.running:
            time.sleep(0.1)

    async def start_all_nodes(self) -> None:
        try:
            for node in self.all_nodes:
                self.run_threaded_node(node)

            print('All Nodes Started.')
        except Exception as err:
            print(err)

    async def stop_all_nodes(self) -> None:
        tasks = []
        for node in self.all_nodes:
            tasks.append(asyncio.ensure_future(node.stop()))

        await asyncio.gather(*tasks)

class TestLocalNodeNetwork(unittest.TestCase):
    def setUp(self):
        self.network = None

        try:
            self.loop = asyncio.get_event_loop()

            if self.loop.is_closed():
                self.loop = None
        except:
            self.loop = None
        finally:
            if not self.loop:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

    def tearDown(self):
        if self.network:
            task = asyncio.ensure_future(self.network.stop_all_nodes())

            while not task.done():
                self.loop.run_until_complete(asyncio.sleep(0.1))

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def create_and_start_threaded_node(self, node_type: str, node_wallet: Wallet):
        node = self.network.create_node(node_type=node_type, node_wallet=node_wallet)
        self.network.run_threaded_node(node=node)

    def test_can_create_instance__raises_no_errors(self):
        try:
            self.network = LocalNodeNetwork()
        except:
            self.fail("Creating a Local Node Network instance should raise no errors.")

        self.assertIsInstance(self.network, LocalNodeNetwork)

    def test_can_add_and_create_a_node_instance_inside_thread(self):
        wallet = Wallet()

        self.network = LocalNodeNetwork(
            constitution={
                'masternodes': [wallet.verifying_key],
                'delegates':[]
            }
        )

        self.create_and_start_threaded_node(node_type='masternode', node_wallet=wallet)

        self.assertEqual(1, self.network.num_of_nodes)
        self.async_sleep(2)
        self.assertIsNotNone(self.network.masternodes[0].node)


    def test_can_start_all_nodes(self):
        wallet_mn_1 = Wallet()
        wallet_mn_2 = Wallet()
        wallet_del_1 = Wallet()
        wallet_del_2 = Wallet()

        self.network = LocalNodeNetwork(
            constitution={
                'masternodes': [wallet_mn_1.verifying_key, wallet_mn_2.verifying_key],
                'delegates': [wallet_del_1.verifying_key, wallet_del_2.verifying_key]
            }
        )

        self.create_and_start_threaded_node(node_type='masternode', node_wallet=wallet_mn_1)
        self.create_and_start_threaded_node(node_type='masternode', node_wallet=wallet_mn_2)
        self.create_and_start_threaded_node(node_type='delegate', node_wallet=wallet_del_1)
        self.create_and_start_threaded_node(node_type='delegate', node_wallet=wallet_del_2)

        self.assertEqual(4, self.network.num_of_nodes)
        self.assertTrue(self.network.all_nodes_started)


    def test_create_new_network__all_node_connect(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=1
        )

        self.assertEqual(2, self.network.num_of_nodes)
        self.assertTrue(self.network.all_nodes_started)

        # Threaded Nodes add all peers
        for tn in self.network.all_nodes:
            connected = False
            while not connected:
                num_of_peers_connected = tn.network.num_of_peers_connected()
                num_of_peers = self.network.num_of_nodes - 1
                connected = num_of_peers_connected == num_of_peers
                self.async_sleep(0.1)






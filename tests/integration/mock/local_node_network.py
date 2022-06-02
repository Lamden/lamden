import asyncio
import json
import random
import time
from typing import List

from tests.integration.mock.threaded_node import ThreadedNode
from tests.integration.mock.mock_data_structures import MockBlocks, MockBlock, MockTransaction
from lamden.crypto.wallet import Wallet
from lamden.storage import BlockStorage
from lamden.nodes.base import Node

from contracting.db.driver import FSDriver

from pathlib import Path
import shutil

import unittest
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from typing import List
import copy

from lamden.nodes.filequeue import FileQueue


MOCK_FOUNDER_SK = '016afd234c03229b44cfb3a067aa6d9ec3cd050774c6eff73aeb0b40cc8e3a12'

class LocalNodeNetwork:
        def __init__(self, constitution: dict={}, bootnodes: list = [], num_of_masternodes: int = 0,
                     num_of_delegates: int = 0, genesis_path: Path = Path.cwd(), should_seed=True):
            self.masternodes: List[Node] = []
            self.delegates: List[Node] = []

            self.constitution = dict(constitution)
            self.bootnodes = dict(bootnodes)

            self.current_path = Path.cwd()
            self.genesis_path = genesis_path
            self.temp_network_dir = Path(f'{self.current_path}/temp_network')

            self.blocks = MockBlocks()

            self.founders_wallet = Wallet(MOCK_FOUNDER_SK)

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
                num_of_masternodes=num_of_masternodes,
                should_seed=should_seed
            )

        @property
        def all_nodes(self) -> List[ThreadedNode]:
            return self.masternodes + self.delegates

        @property
        def all_node_vks(self) -> List[str]:
            return [tn.vk for tn in self.all_nodes]

        @property
        def masternode_vks(self) -> List[str]:
            return [tn.vk for tn in self.masternodes]

        @property
        def num_of_nodes(self) -> int:
            return len(self.all_nodes)

        @property
        def all_nodes_started(self) -> bool:
            nodes_started = list()
            for tn in self.all_nodes:
                if tn.node is None:
                    nodes_started.append(False)
                else:
                    nodes_started.append(tn.node.started)
            return all(n == True for n in nodes_started)

        def get_node(self, vk: str) -> ThreadedNode:
            for tn in self.all_nodes:
                if tn.vk == vk:
                    return tn

        def get_masternode(self, vk: str) -> ThreadedNode:
            for tn in self.masternodes:
                if tn.vk == vk:
                    return tn

        def create_new_network(self, num_of_masternodes: int = 0, num_of_delegates: int = 0, should_seed=True):
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
                    index=node_info[2],
                    should_seed=should_seed
                )
                tn.start()
                while tn.node is None:
                    self.loop.run_until_complete(asyncio.sleep(0.1))

            timeout = 20
            start_time = time.time()

            print("NETWORK ASYNC SLEEPING TO WAIT FOR ALL NODES TO START")
            while not self.all_nodes_started:
                curr_time = time.time()
                elapsed = curr_time - start_time
                if elapsed > timeout:
                    print (f"Hit {timeout} second timeout waiting for all nodes to connect!")
                    break
                else:
                    time.sleep(1)

            print('done')


        def create_constitution(self, node_wallets: list = []):
            return {
                'masternodes': [m[1].verifying_key for m in node_wallets if m[0] == "masternode"],
                'delegates': [d[1].verifying_key for d in node_wallets if d[0] == "delegate"],
            }

        def create_node(self, node_type, index: int = None, node_wallet: Wallet = Wallet(), should_seed: bool = True, node: ThreadedNode = None, reconnect_attempts=60):

            assert node_type in ['masternode', 'delegate'], "node_type must be 'masternode' or 'delegate'"

            node_dir = Path(f'{self.temp_network_dir}/{node_wallet.verifying_key}')
            node_state_dir = Path(f'{node_dir}/state')

            node_state_dir.mkdir(parents=True, exist_ok=True)

            raw_driver = FSDriver(root=Path(node_state_dir))
            block_storage = BlockStorage(home=Path(node_dir))

            tx_queue = FileQueue(root=node_dir.joinpath('txq'))

            if not node:
                node = ThreadedNode(
                    index=index or self.num_of_nodes,
                    node_type=node_type,
                    wallet=node_wallet,
                    constitution=self.constitution,
                    bootnodes=self.bootnodes,
                    raw_driver=raw_driver,
                    block_storage=block_storage,
                    genesis_path=self.genesis_path,
                    should_seed=should_seed,
                    tx_queue=tx_queue,
                    reconnect_attempts=reconnect_attempts
                )

            if node.node_type == 'masternode':
                self.masternodes.append(node)

            if node.node_type == 'delegate':
                self.delegates.append(node)

            return node

        def add_new_node_to_network(self, node_type: str, bootnodes: ThreadedNode = None, should_seed=False, reconnect_attempts=60):
            new_node_wallet = Wallet()
            new_node_vk = new_node_wallet.verifying_key
            index = self.num_of_nodes

            self.add_new_node_vk_to_network(node_type=node_type, vk=new_node_vk)

            node = self.create_node(
                node_type=node_type,
                node_wallet=new_node_wallet,
                should_seed=should_seed,
                reconnect_attempts=reconnect_attempts
            )

            if bootnodes:
                node.bootnodes = bootnodes
            else:
                node.bootnodes = self.make_bootnode(self.masternodes[0])
                if should_seed:
                    self.constitution[f'{node_type}s'].append(new_node_vk)

            self.run_threaded_node(node)

            return node

        def add_masternode(self, should_seed=False, reconnect_attempts=60):
            return self.add_new_node_to_network(node_type="masternode", should_seed=should_seed,
                reconnect_attempts=reconnect_attempts)

        def add_delegate(self):
            return self.add_new_node_to_network(node_type="delegate")

        def add_new_node_vk_to_network(self, node_type: str, vk: str):
            node_list = getattr(self, f'{node_type}s')
            node_vks = [tn.vk for tn in node_list]
            node_vks.append(vk)
            for tn in self.all_nodes:
                tn.set_smart_contract_value(
                    key=f'{node_type}s.S:members',
                    value=node_vks
                )
                tn.network.refresh_approved_peers_in_cred_provider()

        def make_bootnode(self, node: ThreadedNode):
            return {node.vk: node.ip}

        def add_blocks_to_network(self, num_of_blocks: int):
            for i in range(num_of_blocks):
                self.add_new_block_to_network()

        def add_new_block_to_network(self):
            self.blocks.add_block()
            self.add_block_to_nodes(vks=self.all_node_vks, block=self.blocks.get_latest_block())

        def add_block_to_node(self, vk: str, block: MockBlock):
            tn = self.get_node(vk=vk)
            tn.node.blocks.store_block(block=copy.deepcopy(block))
            tn.node.update_block_db(block=block)
            tn.node.apply_state_changes_from_block(block=block)

        def add_block_to_nodes(self, vks: List[str], block: MockBlock):
            for vk in vks:
                self.add_block_to_node(vk=vk, block=block)

        def send_tx_to_random_masternode(self, **kwargs):
            if kwargs.get('processor'):
                kwargs.pop('processor')

            tx = self.create_new_currency_transaction(**kwargs)
            self.send_tx(tx=tx)

        def send_tx_to_masternode(self, masternode_vk, **kwargs):
            kwargs['processor'] = masternode_vk
            tx = self.create_new_currency_transaction(**kwargs)
            self.send_tx(tx=tx)

        def create_new_currency_transaction(self,
                                            sender_wallet: Wallet = None,
                                            receiver_vk: str = Wallet().verifying_key,
                                            amount: str = {'__fixed__': '10.5'},
                                            nonce: int = 0,
                                            processor: str = None,
                                            stamps_supplied: int = 20
                                            ):
            tx = MockTransaction()
            tx.create_transaction(
                sender_wallet=sender_wallet or self.founders_wallet,
                contract="currency",
                function="transfer",
                kwargs={
                    'amount': amount,
                    'to': receiver_vk
                },
                nonce=nonce,
                processor=processor or random.choice(self.masternode_vks),
                stamps_supplied=stamps_supplied
            )
            return tx

        def send_tx(self, tx: MockTransaction):
            processor = tx.get_processor()
            tn = self.get_masternode(vk=processor)
            if tn is None:
                return
            tx_dict = tx.as_dict()
            encoded_tx=json.dumps(tx_dict).encode('UTF-8')
            tn.send_tx(encoded_tx=encoded_tx)

        def pause_all_validation_queues(self):
            for tn in self.all_nodes:
                tn.node.validation_queue.pause()

        def unpause_all_validation_queues(self):
            for tn in self.all_nodes:
                tn.node.validation_queue.unpause()

        def pause_all_processing_queues(self):
            for tn in self.all_nodes:
                tn.node.main_processing_queue.pause()

        def unpause_all_processing_queues(self):
            for tn in self.all_nodes:
                tn.node.main_processing_queue.unpause()

        def pause_all_queues(self):
            self.pause_all_validation_queues()
            self.pause_all_processing_queues()

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

        self.loop.stop()
        self.loop.close()

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

        num_of_masternodes = 4
        num_of_delegates = 4

        self.network.create_new_network(
            num_of_masternodes=num_of_masternodes,
            num_of_delegates=num_of_delegates
        )

        self.assertEqual(num_of_masternodes + num_of_delegates, self.network.num_of_nodes)
        self.assertTrue(self.network.all_nodes_started)

        timeout = 60
        start_time = time.time()

        # Threaded Nodes add all peers
        for tn in self.network.all_nodes:
            connected = False
            while not connected:
                num_of_peers_connected = tn.network.num_of_peers_connected()
                num_of_peers = self.network.num_of_nodes - 1
                connected = num_of_peers_connected == num_of_peers

                if time.time() - start_time > timeout:
                    self.fail(f"Hit {timeout} second timeout waiting for all nodes to add peers!")
                else:
                    self.async_sleep(0.1)

    def test_add_new_node_to_network__new_node_connects_and_all_existing_connect_back_to_it(self):
        self.network = LocalNodeNetwork()

        num_of_masternodes = 1
        num_of_delegates = 1
        total_num_of_nodes = num_of_masternodes + num_of_delegates

        self.network.create_new_network(
            num_of_masternodes=num_of_masternodes,
            num_of_delegates=num_of_delegates
        )

        self.assertEqual(total_num_of_nodes, self.network.num_of_nodes)
        self.async_sleep(2)
        self.assertTrue(self.network.all_nodes_started)

        new_node = self.network.add_new_node_to_network(node_type='masternode')

        self.assertEqual(total_num_of_nodes + 1, self.network.num_of_nodes)

        while not self.network.all_nodes_started:
            self.async_sleep(1)

        self.assertTrue(self.network.all_nodes_started)

        self.async_sleep(5)
        self.assertTrue(new_node.network.all_peers_connected())


    def test_add_new_node_vk_to_network(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=0
        )

        self.async_sleep(0.5)
        self.assertTrue(self.network.all_nodes_started)


        self.network.add_new_node_to_network(node_type='delegate')

        existing_node =self.network.masternodes[0]
        new_node = self.network.delegates[0]

        while existing_node.latest_block_height != new_node.latest_block_height:
            self.async_sleep(60)


    def test_testcase_can_preload_blocks(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=0
        )

        self.network.add_blocks_to_network(num_of_blocks=5)
        self.assertEqual(5, self.network.masternodes[0].node.get_current_height())

    def test_testcase_preloading_can_add_state(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=0
        )

        self.network.add_blocks_to_network(num_of_blocks=5)
        self.assertEqual(5, self.network.masternodes[0].node.get_current_height())

        node = self.network.all_nodes[0]

        for vk, amount in self.network.blocks.internal_state.items():
            print(f'node vk: {node.vk}')
            print(vk, str(amount))
            state_amount = node.get_smart_contract_value(key=f'currency.balances:{vk}')
            self.assertEqual(amount, state_amount)

    def test_can_create_and_send_tx_to_masternode(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=0
        )

        tn = self.network.masternodes[0]
        tn.node.pause_tx_queue()

        self.network.send_tx_to_masternode(masternode_vk=tn.vk)

        self.async_sleep(1)

        self.assertEqual(1, len(tn.node.tx_queue))


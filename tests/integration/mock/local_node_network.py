from contracting.db.driver import FSDriver, InMemDriver
from contracting.db.encoder import encode
from lamden.crypto.wallet import Wallet
from lamden.nodes.base import Node
from lamden.nodes.filequeue import FileQueue
from lamden.storage import BlockStorage, NonceStorage
from pathlib import Path
from tests.integration.mock.mock_data_structures import MockBlocks, MockBlock, MockTransaction
from tests.integration.mock.threaded_node import ThreadedNode
from typing import List
import asyncio
import copy
import json
import random
import shutil
import time
import unittest
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

MOCK_FOUNDER_SK = '016afd234c03229b44cfb3a067aa6d9ec3cd050774c6eff73aeb0b40cc8e3a12'

class LocalNodeNetwork:
        def __init__(self, constitution: dict = {}, genesis_block: dict = None, bootnodes: list = [],
                     num_of_masternodes: int = 0, delay=None):
            self.masternodes: List[Node] = []

            self.constitution = dict(constitution)
            self.bootnodes = dict(bootnodes)
            self.genesis_block = genesis_block

            self.current_path = Path.cwd()
            self.temp_network_dir = self.current_path.joinpath('temp_network')

            self.founders_wallet = Wallet(MOCK_FOUNDER_SK)

            self.blocks = MockBlocks(founder_wallet=self.founders_wallet)

            self.nonces = {}
            if self.temp_network_dir.is_dir():
                shutil.rmtree(self.temp_network_dir)

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

            self.delay = delay

            self.create_new_network(
                num_of_masternodes=num_of_masternodes
            )

        def __del__(self):
            if self.temp_network_dir.is_dir():
                shutil.rmtree(self.temp_network_dir)

        @property
        def all_nodes(self) -> List[ThreadedNode]:
            return self.masternodes

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

        def create_new_network(self, num_of_masternodes: int = 0):
            if num_of_masternodes == 0:
                return

            node_wallets = masternode_wallets = [("masternode", Wallet(), m) for m in range(num_of_masternodes)]

            self.constitution = self.create_constitution(
                node_wallets=node_wallets
            )

            for node_info in node_wallets:
                self.bootnodes[node_info[1].verifying_key] = f'tcp://127.0.0.1:{19000 + node_info[2]}'

            genesis_block = self.genesis_block

            if genesis_block is None:
                self.blocks.initial_members = {
                    'masternodes': [wallet[1].verifying_key for wallet in masternode_wallets],
                }
                self.blocks.add_blocks(num_of_blocks=1)
                genesis_block = self.blocks.get_block_by_index(index=0)
            else:
                self.blocks.add_to_blocks_dict(block=genesis_block)

            for node_info in node_wallets:
                tn = self.create_node(
                    node_wallet=node_info[1],
                    genesis_block=genesis_block,
                    index=node_info[2]
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
                'masternodes': [m[1].verifying_key for m in node_wallets if m[0] == "masternode"]
            }

        def create_node(self, genesis_block: dict=None, index: int = None, node_wallet: Wallet = Wallet(),
                        node: ThreadedNode = None, reconnect_attempts=60):

            node_dir = Path(f'{self.temp_network_dir}/{node_wallet.verifying_key}')

            #raw_driver = FSDriver(root=node_dir)
            raw_driver = InMemDriver()
            block_storage = BlockStorage(root=node_dir)
            nonce_storage = NonceStorage(root=node_dir)
            tx_queue = FileQueue(root=node_dir)

            if not node:
                node = ThreadedNode(
                    index=index or self.num_of_nodes,
                    wallet=node_wallet,
                    constitution=self.constitution,
                    bootnodes=self.bootnodes,
                    raw_driver=raw_driver,
                    block_storage=block_storage,
                    nonce_storage=nonce_storage,
                    genesis_block=genesis_block,
                    tx_queue=tx_queue,
                    reconnect_attempts=reconnect_attempts,
                    delay=self.delay
                )

            self.masternodes.append(node)

            return node

        def add_new_node_to_network(self, genesis_block: dict = None, bootnodes: ThreadedNode = None, reconnect_attempts=60, wallet=None):
            new_node_wallet = wallet if wallet is not None else Wallet()
            new_node_vk = new_node_wallet.verifying_key

            self.add_new_node_vk_to_network(vk=new_node_vk)

            node = self.create_node(
                node_wallet=new_node_wallet,
                reconnect_attempts=reconnect_attempts,
                genesis_block=genesis_block
            )

            if bootnodes:
                node.bootnodes = bootnodes
            else:
                node.bootnodes = self.make_bootnode(self.masternodes[0])
                if genesis_block:
                    self.constitution['masternodes'].append(new_node_vk)

            self.run_threaded_node(node)

            return node

        def add_masternode(self, genesis_block: dict=None, reconnect_attempts=60, wallet=None):
            return self.add_new_node_to_network(genesis_block=genesis_block, reconnect_attempts=reconnect_attempts, wallet=wallet)

        def add_new_node_vk_to_network(self, vk: str):
            node_vks = [tn.vk for tn in self.all_nodes]
            if vk not in node_vks:
                node_vks.append(vk)
            for tn in self.all_nodes:
                tn.set_smart_contract_value(
                    key='masternodes.S:members',
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

            return tx.as_dict()

        def send_tx_to_masternode(self, masternode_vk, **kwargs):
            kwargs['processor'] = masternode_vk
            tx = self.create_new_currency_transaction(**kwargs)
            self.send_tx(tx=tx)

        def create_new_currency_transaction(self,
                                            sender_wallet: Wallet = None,
                                            receiver_vk: str = Wallet().verifying_key,
                                            amount: str = {'__fixed__': '10.5'},
                                            processor: str = None,
                                            stamps_supplied: int = 20
                                            ):
            tx = MockTransaction()
            nonce = self.nonces.get(sender_wallet)
            if nonce is None:
                self.nonces[sender_wallet] = 0
            else:
                self.nonces[sender_wallet] += 1

            nonce = self.nonces[sender_wallet]

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

            return encoded_tx

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

            running_tasks = await asyncio.gather(*tasks)

            for node in self.all_nodes:
                node.join()

            print("All Nodes Stopped.")

        def await_all_nodes_done_processing(self, block_height, timeout=360, nodes=None):
            done = False
            start = time.time()
            while not done:
                if 0 < timeout < time.time() - start:
                    print(f'{__name__} TIMED OUT')
                    break
                results = [tn.node.blocks.total_blocks() == block_height for tn in (nodes if nodes is not None else self.all_nodes)]
                done = all(results)
                loop = asyncio.get_event_loop()
                loop.run_until_complete(asyncio.sleep(1))

            print(f'!!!!! ALL NODES AT BLOCK {block_height} !!!!!')
        
        def get_var_from_one(self, key:str, tn: ThreadedNode):
            return tn.raw_driver.get(key)

        def get_var_from_all(self, key=str):
            return [self.get_var_from_one(key, tn) for tn in self.all_nodes]

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
            for tn in self.network.all_nodes:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(tn.stop())

            for tn in self.network.all_nodes:
                tn.join()

        self.loop.stop()
        self.loop.close()

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def create_and_start_threaded_node(self, node_wallet: Wallet, genesis_block: dict = None):
        node = self.network.create_node(node_wallet=node_wallet, genesis_block=genesis_block)
        self.network.run_threaded_node(node=node)

    def test_can_create_instance__raises_no_errors(self):
        try:
            self.network = LocalNodeNetwork()
        except:
            self.fail("Creating a Local Node Network instance should raise no errors.")

        self.assertIsInstance(self.network, LocalNodeNetwork)

    def test_2can_add_and_create_a_node_instance_inside_thread(self):
        wallet = Wallet()

        self.network = LocalNodeNetwork(
            constitution={
                'masternodes': [wallet.verifying_key],
                'delegates':[]
            }
        )

        self.create_and_start_threaded_node(node_wallet=wallet)

        self.assertEqual(1, self.network.num_of_nodes)
        self.async_sleep(2)
        self.assertIsNotNone(self.network.masternodes[0].node)

    def test_can_start_all_nodes(self):
        wallet_mn_1 = Wallet()
        wallet_mn_2 = Wallet()
        wallet_del_1 = Wallet()
        wallet_del_2 = Wallet()

        constitution = {
            'masternodes': [wallet_mn_1.verifying_key, wallet_mn_2.verifying_key, wallet_del_1.verifying_key, wallet_del_2.verifying_key]
        }

        self.network = LocalNodeNetwork(
            constitution=constitution
        )
        self.network.blocks.initial_members = constitution
        self.network.blocks.add_blocks(num_of_blocks=1)
        genesis_block = self.network.blocks.get_block_by_index(index=0)

        self.create_and_start_threaded_node(node_wallet=wallet_mn_1, genesis_block=genesis_block)
        self.create_and_start_threaded_node(node_wallet=wallet_mn_2, genesis_block=genesis_block)
        self.create_and_start_threaded_node(node_wallet=wallet_del_1, genesis_block=genesis_block)
        self.create_and_start_threaded_node(node_wallet=wallet_del_2, genesis_block=genesis_block)

        self.assertEqual(4, self.network.num_of_nodes)
        self.assertTrue(self.network.all_nodes_started)

    def test_3create_new_network__all_node_connect(self):
        self.network = LocalNodeNetwork()

        num_of_masternodes = 2

        self.network.create_new_network(
            num_of_masternodes=num_of_masternodes
        )

        self.assertEqual(num_of_masternodes, self.network.num_of_nodes)
        self.assertTrue(self.network.all_nodes_started)

        # Threaded Nodes add all peers
        for tn in self.network.all_nodes:
            timeout = 20
            start_time = time.time()

            connected = False
            while not connected:
                num_of_peers_connected = tn.network.num_of_peers_connected()
                num_of_peers = self.network.num_of_nodes - 1
                connected = num_of_peers_connected == num_of_peers

                if connected:
                    break

                if time.time() - start_time > timeout:
                    self.fail(f"Hit {timeout} second timeout waiting for all nodes to add peers!")
                else:
                    self.async_sleep(5)

        for tn in self.network.all_nodes:
            self.assertTrue(tn.node.network.connected_to_all_peers())
    def test_add_new_node_to_network__new_node_connects_and_all_existing_connect_back_to_it(self):
        self.network = LocalNodeNetwork()

        num_of_masternodes = 2

        self.network.create_new_network(
            num_of_masternodes=num_of_masternodes
        )

        self.assertEqual(num_of_masternodes, self.network.num_of_nodes)
        self.async_sleep(2)
        self.assertTrue(self.network.all_nodes_started)

        new_node = self.network.add_new_node_to_network()

        self.assertEqual(num_of_masternodes + 1, self.network.num_of_nodes)

        while not self.network.all_nodes_started:
            self.async_sleep(1)

        self.assertTrue(self.network.all_nodes_started)

        self.async_sleep(5)
        self.assertTrue(new_node.network.all_peers_connected())

    
    def test_add_new_node_vk_to_network(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1
        )

        self.async_sleep(0.5)
        self.assertTrue(self.network.all_nodes_started)

        self.network.add_new_node_to_network()

        existing_node =self.network.masternodes[0]
        new_node = self.network.masternodes[1]

        self.assertEqual(existing_node.latest_block_height, new_node.latest_block_height)

    def test_testcase_can_preload_blocks(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1
        )

        self.network.add_blocks_to_network(num_of_blocks=5)
        self.assertEqual(6, self.network.masternodes[0].node.blocks.total_blocks())

    def test_testcase_preloading_can_add_state(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1
        )

        self.network.add_blocks_to_network(num_of_blocks=5)
        self.assertEqual(6, self.network.masternodes[0].node.blocks.total_blocks())

        node = self.network.all_nodes[0]

        for key, value in self.network.blocks.internal_state.items():
            self.assertEqual(value, node.get_smart_contract_value(key=key))

    def test_1can_create_and_send_tx_to_masternode(self):
        self.network = LocalNodeNetwork()

        self.network.create_new_network(
            num_of_masternodes=1
        )

        tn = self.network.masternodes[0]
        tn.node.pause_tx_queue()

        self.network.send_tx_to_masternode(masternode_vk=tn.vk)

        self.async_sleep(1)

        self.assertEqual(1, len(tn.node.tx_queue))

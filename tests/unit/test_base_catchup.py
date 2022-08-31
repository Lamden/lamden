from unittest import TestCase
import shutil
from pathlib import Path

from lamden.nodes.base import Node

from lamden.storage import BlockStorage, NonceStorage, set_latest_block_height
from contracting.db.driver import ContractDriver, FSDriver, InMemDriver
from lamden.nodes.filequeue import FileQueue
from lamden.utils import hlc
from lamden.crypto.wallet import Wallet
from lamden.utils import create_genesis

from tests.integration.mock.mock_data_structures import MockBlocks
from tests.unit.helpers.mock_transactions import get_processing_results, get_tx_message

from typing import List


import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class Peer:
    def __init__(self, blocks: list):
        self.blocks = blocks
        self.wallet = Wallet()
        self.return_bad_latest_block = False
        self.hard_code_latest_block = 0

    @property
    def server_vk(self):
        return self.wallet.verifying_key

    @property
    def latest_block_number(self):
        self.blocks.sort(key=lambda x: x.get('number'))

        if self.return_bad_latest_block:
            return int(self.blocks[-1].get('number')) + 1
        else:
            if self.hard_code_latest_block > 0:
                return self.hard_code_latest_block
            else:
                return int(self.blocks[-1].get('number'))

    async def get_next_block(self, block_num: int):
        later_blocks = list(filter(lambda x: int(x.get('number')) > int(block_num), self.blocks))
        later_blocks.sort(key=lambda x: x.get('number'))
        try:
            return self.wrap_response(block_info=later_blocks[0])
        except:
            return self.wrap_response(block_info=None)

    def wrap_response(self, block_info):
        return {'block_info': block_info}

class TestBaseNode_Catchup(TestCase):
    def setUp(self):
        self.current_path = Path.cwd()
        self.genesis_path = Path(f'{self.current_path.parent}/integration/mock')
        self.temp_storage = Path(f'{self.current_path}/temp_storage')

        self.node_wallet = Wallet()
        self.genesis_block = create_genesis.build_block(
            founder_sk='beef' * 16,
            additional_state={'masternodes.S:members': [self.node_wallet.verifying_key]}
        )

        if self.temp_storage.is_dir():
            shutil.rmtree(self.temp_storage)
        self.temp_storage.mkdir(exist_ok=True, parents=True)


        self.initial_members = {
            'masternodes': [self.node_wallet.verifying_key]
        }

        self.node = None
        self.mock_blocks = MockBlocks(num_of_blocks=10, one_wallet=True, initial_members=self.initial_members)
        self.catchup_peers: List[Peer] = []

    def tearDown(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.stop())

        del self.node
        if self.temp_storage.is_dir():
            shutil.rmtree(self.temp_storage)

    def create_node_instance(self, genesis_block=False) -> Node:
        node_wallet = Wallet()
        node_dir = Path(f'{self.temp_storage}/{node_wallet.verifying_key}')
        # node_state_dir = Path(f'{node_dir}/state')
        raw_driver = InMemDriver()
        contract_driver = ContractDriver(driver=raw_driver)
        block_storage = BlockStorage(root=node_dir)
        nonce_storage = NonceStorage(root=node_dir)

        tx_queue = FileQueue(root=node_dir)

        constitution = {
            'masternodes': {self.node_wallet.verifying_key: 'tcp://127.0.0.1:19000'}
        }

        if genesis_block:
            genesis_block_data = self.genesis_block
        else:
            genesis_block_data = None

        return Node(
            constitution=constitution,
            bootnodes={},
            socket_base="",
            wallet=self.node_wallet,
            socket_ports=self.create_socket_ports(index=0),
            driver=contract_driver,
            blocks=block_storage,
            tx_queue=tx_queue,
            testing=True,
            nonces=nonce_storage,
            genesis_block=genesis_block_data
        )

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def get_catchup_peers(self):
        return self.catchup_peers

    def mock_get_highest_peer_blocks(self):
        highest_block_num = 0
        for peer in self.catchup_peers:
            if peer.latest_block_number > highest_block_num:
                highest_block_num = peer.latest_block_number
        return highest_block_num

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_node_instance(self):
        self.node = self.create_node_instance()
        self.assertIsNotNone(self.node)

    def test_can_start_node_instance(self):
        self.node = self.create_node_instance(genesis_block=True)
        try:
            self.node.start_node()
        except Exception:
            self.fail('Node should not throw exceptions on startup')

        self.async_sleep(1)
        self.assertTrue(self.node.running)

    def test_catchup_get_blocks__gets_blocks_from_peers(self):
        self.node = self.create_node_instance()
        latest_block_num = self.mock_blocks.latest_block_num

        for i in range(5):
            peer = Peer(blocks=self.mock_blocks.get_blocks())
            self.catchup_peers.append(peer)

        loop = asyncio.get_event_loop()

        loop.run_until_complete(self.node.catchup_get_blocks(
            catchup_peers=self.catchup_peers,
            catchup_stop_block=latest_block_num
        ))

        while self.node.get_current_height() != latest_block_num:
            self.async_sleep(1)

    def test_catchup_get_blocks__no_peer_responds_with_block_rasies_ConnectionError(self):
        self.node = self.create_node_instance()
        for i in range(5):
            peer = Peer(blocks=self.mock_blocks.get_blocks())
            self.catchup_peers.append(peer)

        latest_block_num = self.mock_blocks.latest_block_num

        for peer in self.catchup_peers:
            peer.return_bad_latest_block = True

        with self.assertRaises(ConnectionError):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.node.catchup_get_blocks(
                catchup_peers=self.catchup_peers,
                catchup_stop_block=latest_block_num + 1
            ))

    def test_catchup_continuous__raises_ValueError_if_no_catchup_peers_are_available(self):
        self.node = self.create_node_instance()
        for i in range(5):
            peer = Peer(blocks=self.mock_blocks.get_blocks())
            self.catchup_peers.append(peer)

        self.node.network.get_all_connected_peers = lambda: []
        self.node.network.get_highest_peer_block = self.mock_get_highest_peer_blocks

        with self.assertRaises(ValueError):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.node.catchup_continuous(
                block_threshold=0
            ))


    def test_catchup_continuous__node_stops_catchup_at_block_threshold(self):
        self.node = self.create_node_instance()
        for i in range(5):
            peer = Peer(blocks=self.mock_blocks.get_blocks())
            self.catchup_peers.append(peer)

        self.node.network.get_all_connected_peers = self.get_catchup_peers
        self.node.network.get_highest_peer_block = self.mock_get_highest_peer_blocks

        block_threshold = 5

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.catchup_continuous())

        self.async_sleep(1)

        block_difference = self.node.blocks.total_blocks() - len(self.mock_blocks.blocks)

        self.assertLessEqual(block_difference, block_threshold)

    def test_catchup_to_validation_queue__waits_for_validation_queue_to_mint_a_block_before_continuing(self):
        self.node = self.create_node_instance()
        self.node.started = True
        self.node.network.get_all_connected_peers = self.get_catchup_peers
        self.node.network.get_highest_peer_block = self.mock_get_highest_peer_blocks

        for i in range(5):
            peer = Peer(blocks=self.mock_blocks.get_blocks())
            self.catchup_peers.append(peer)

        task = asyncio.ensure_future(self.node.catchup_to_validation_queue())

        self.async_sleep(2)

        self.assertFalse(task.done())

        hlc_timestamp = self.mock_blocks.latest_hlc_timestamp

        tx_message = get_tx_message(
            hlc_timestamp=hlc_timestamp
        )

        self.node.driver.driver.set('masternodes.S:members', [tx_message['tx']['payload']['processor']])

        processing_results_1 = get_processing_results(tx_message=tx_message)
        processing_results_2 = get_processing_results(tx_message=tx_message)

        self.node.validation_queue.append(processing_results_1)
        self.node.validation_queue.append(processing_results_2)

        while not task.done():
            self.async_sleep(1)

        # Make sure stop was not called
        self.assertTrue(self.node.started)
        self.assertTrue(task.done())

    def test_catchup_to_validation_queue__catchup_from_last_received_to_last_minted_block(self):
        self.node = self.create_node_instance()
        loop = asyncio.get_event_loop()
        # Peers need some blocks
        for i in range(5):
            peer = Peer(blocks=self.mock_blocks.get_blocks())
            self.catchup_peers.append(peer)

        self.node.started = True
        self.node.network.get_all_connected_peers = self.get_catchup_peers
        self.node.network.get_highest_peer_block = self.mock_get_highest_peer_blocks

        # Add some blocks to the node to simulate an initial catchup
        for i in range(2):
            block = self.mock_blocks.get_block_by_index(i)
            loop.run_until_complete(
                self.node.hard_apply_block(block=self.mock_blocks.get_block_by_index(i))
            )
            self.assertEqual(int(block.get('number')), self.node.get_current_height())
        self.assertTrue(2, self.node.blocks.total_blocks())

        # Send some results to the validation queue
        last_block = self.mock_blocks.get_block_by_index(len(self.mock_blocks.blocks) - 1)

        hlc_timestamp = last_block.get('hlc_timestamp')
        tx_message = get_tx_message(
            hlc_timestamp=hlc_timestamp
        )
        current_members = self.node.driver.driver.get(item='masternodes.S:members')
        current_members.append(tx_message['tx']['payload']['processor'])
        self.node.driver.driver.set('masternodes.S:members', current_members)
        for i in range(2):
            processing_results = get_processing_results(tx_message=tx_message)
            self.node.validation_queue.append(processing_results)

        # set the latest block higher for all the catchup peers to mimic them also processing these blocks
        for peer in self.catchup_peers:
            peer.hard_code_latest_block = hlc.nanos_from_hlc_timestamp(hlc_timestamp)

        loop.run_until_complete(self.node.catchup_to_validation_queue())

        # node has the 10 blocks.
        self.assertEqual(10, self.node.blocks.total_blocks())

        # Make sure stop was not called
        self.assertTrue(self.node.started)

    def test_catchup__can_catchup_from_peers(self):
        self.node = self.create_node_instance()
        self.node.network.get_all_connected_peers = self.get_catchup_peers
        self.node.network.get_highest_peer_block = self.mock_get_highest_peer_blocks

        for i in range(5):
            peer = Peer(blocks=self.mock_blocks.get_blocks())
            self.catchup_peers.append(peer)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.catchup())

        self.assertEqual(self.mock_blocks.latest_block_num, self.node.get_current_height())

    def test_catchup__raises_ValueError_if_no_peers_are_available(self):
        self.node = self.create_node_instance()
        with self.assertRaises(ValueError):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.node.catchup())


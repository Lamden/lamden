import os.path

from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.integration.mock.mock_data_structures import MockBlocks
from lamden.crypto.wallet import Wallet

from unittest import TestCase
import asyncio
import copy
import uvloop

from contracting.db.encoder import decode
import time

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNewNodeCatchup(TestCase):
    def setUp(self):
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

        self.test_tracker = {}
        self.network = LocalNodeNetwork()

    def tearDown(self):
        task = asyncio.ensure_future(self.network.stop_all_nodes())
        while not task.done():
            self.loop.run_until_complete(asyncio.sleep(0.1))

        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def send_transactions_to_network(self, amount_of_transactions: int, receiver_wallet:Wallet = Wallet()):
        for i in range(amount_of_transactions):
            self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk= receiver_wallet.verifying_key
            )

    def send_transactions_to_masternode(self, amount_of_transactions: int, masternode_vk: str,
                                        receiver_wallet:Wallet = Wallet()):

        for i in range(amount_of_transactions):
            self.local_node_network.send_tx_to_masternode(
                masternode_vk=masternode_vk,
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk= receiver_wallet.verifying_key
            )


    async def mock_process_subscription(self, data):
        print('mock_process_subscription')
        pass

    def test_node_picks_up_missing_block_after_hard_applying(self):

        num_of_masternodes = 3
        amount_of_transactions = 2

        self.local_node_network = LocalNodeNetwork(
            num_of_masternodes=num_of_masternodes,
            network_await_connect_all_timeout=5
        )

        self.send_transactions_to_network(amount_of_transactions=amount_of_transactions)

        # wait till all nodes reach the required block height
        self.local_node_network.await_all_nodes_done_processing(block_height=amount_of_transactions+1)

        # Prevent a node from getting the next block by over-writting it's subscription processor
        for peer in self.local_node_network.masternodes[0].network.peer_list:
            peer.subscriber.callback = self.mock_process_subscription

        self.send_transactions_to_masternode(
            amount_of_transactions=1,
            masternode_vk=self.local_node_network.masternodes[1].wallet.verifying_key
        )

        self.async_sleep(2)

        missing_block = self.local_node_network.masternodes[1].network.get_latest_block()
        missing_block_number = missing_block.get('number')

        for peer in self.local_node_network.masternodes[0].network.peer_list:
            peer.subscriber.callback = peer.process_subscription

        self.send_transactions_to_network(amount_of_transactions=1)
        self.async_sleep(2)

        # Node made aware of missing block
        missing_block_file_path = os.path.join(self.local_node_network.masternodes[0].node.missing_blocks_handler.missing_blocks_dir, missing_block_number)
        self.assertTrue(os.path.exists(missing_block_file_path))
        self.assertIsNone(self.local_node_network.masternodes[0].blocks.get_block(v= int(missing_block_number)))

        # Send another tx
        self.send_transactions_to_network(amount_of_transactions=1)
        self.async_sleep(2)

        self.assertFalse(os.path.exists(missing_block_file_path))
        self.assertIsNotNone(self.local_node_network.masternodes[0].node.blocks.get_block(v=int(missing_block_number)))




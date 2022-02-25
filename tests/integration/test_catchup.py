'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    THROUGHPUT Test send all transactions AT ONCE and then wait for all nodes to process them and come to consensus
    After all node are in sync then the test are run to validate state etc.

'''
from tests.integration.mock import mocks_new
from lamden.crypto.wallet import Wallet
from contracting.db.encoder import encode

import zmq.asyncio
import asyncio
import json

from unittest import TestCase

def make_block(block_num, hlc_timestamp):
    return {
        "number": block_num,
        "hash": str(block_num),
        "hlc_timestamp": hlc_timestamp,
        "processed": {
            'hash': str(block_num),
            'state': [{
                'key': 'testing.test:test',
                'value': block_num
            }]
        }
}


class TestMultiNode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.n = None

    def tearDown(self):
        if self.n:
            for node in self.n.nodes:
                self.await_async_process(node.stop)

        self.ctx.destroy()
        self.loop.close()

    def await_async_process(self, process):
        tasks = asyncio.gather(
            process()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def send_transaction(self, node, tx):
        node.tx_queue.append(tx)


    def test_node_can_catchup(self):
        delay = {'base': 0.1, 'self': 0.2}
        self.n = mocks_new.MockNetwork(num_of_delegates=1, num_of_masternodes=1, ctx=self.ctx, metering=False,
                                       delay=delay)

        # Start network
        self.await_async_process(self.n.start)
        self.async_sleep(1)
        masternode_vk = self.n.masternodes[0].obj.wallet.verifying_key

        # Add blocks to masternode
        for n in range(5):
            block = make_block(
                block_num=n+1,
                hlc_timestamp=self.n.masternodes[0].obj.hlc_clock.get_new_hlc_timestamp()
            )
            # self.await_hard_apply_block(node=self.n.masternodes[0].obj, block=block)
            encoded_block = encode(block)
            encoded_block = json.loads(encoded_block)

            self.n.masternodes[0].obj.blocks.store_block(encoded_block)

            # Set the current block hash and height
            self.n.masternodes[0].obj.update_block_db(block=encoded_block)

            # Set the masternodes's known block height on the delegate
            self.n.delegates[0].obj.network.peers[masternode_vk].latest_block_info = {
                'number': block.get('number'),
                'hlc_timestamp': block.get('hlc_timestamp')
            }

        self.assertEqual(self.n.masternodes[0].obj.get_current_height(), 5)

        # Run catchup on the delegate (should pull in all blocks from maternode)
        self.await_async_process(self.n.delegates[0].obj.catchup)

        self.async_sleep(5)

        # Test the blockheight is correct
        self.assertEqual(self.n.delegates[0].obj.get_current_height(), 5)

        # Test the state changes were applied correctly
        state_value = self.n.delegates[0].obj.driver.get_var(
            contract='testing',
            variable='test',
            arguments=['test']
        )
        self.assertEqual(state_value, 5)




from tests.integration.mock import mocks_new

import zmq.asyncio
import asyncio

from unittest import TestCase

class TestMockNetwork(TestCase):
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

    def send_message_to_node(self, node, msg):
        tasks = asyncio.gather(
            node.work_validator.process_message(msg=msg)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def await_join_new_node(self, type_of_node, node=None):
        tasks = asyncio.gather(
            self.n.join_network(type_of_node, node)
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


    def test_single_masternode_network_starts(self):
        delay = {'base': 0.1, 'self': 0.2}
        self.n = mocks_new.MockNetwork(num_of_delegates=0, num_of_masternodes=1, ctx=self.ctx, metering=False,
                                       delay=delay)

        # Start network
        self.await_async_process(self.n.start)
        self.async_sleep(0.5)

        self.assertTrue(self.n.masternodes[0].obj.running)

    def test_single_delegate_network_starts(self):
        delay = {'base': 0.1, 'self': 0.2}
        self.n = mocks_new.MockNetwork(num_of_delegates=1, num_of_masternodes=0, ctx=self.ctx, metering=False,
                                       delay=delay)

        # Start network
        self.await_async_process(self.n.start)
        self.async_sleep(0.5)

        self.assertTrue(self.n.delegates[0].obj.running)

    def test_multinode_network_starts(self):
        delay = {'base': 0.1, 'self': 0.2}
        self.n = mocks_new.MockNetwork(num_of_delegates=4, num_of_masternodes=2, ctx=self.ctx, metering=False,
                                       delay=delay)

        # Start network
        self.await_async_process(self.n.start)
        self.async_sleep(0.5)

        for node in self.n.nodes:
            self.assertEqual(True, node.obj.network.all_peers_connected())

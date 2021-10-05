from tests.integration.mock.mocks_multip import TEST_FOUNDATION_WALLET, Process, MockNetwork, MockMaster, create_fixture_directories, remove_fixture_directories
from lamden.nodes.filequeue import FileQueue

from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.db import encoder

import zmq.asyncio
import asyncio
import httpx
from random import randrange
import json
import time
import pprint
import multiprocessing
from unittest import TestCase
from sys import setrecursionlimit
setrecursionlimit(20000)


class TestMultiNode(TestCase):
    def setUp(self):
        self.fixture_directories = ['block_storage', 'file_queue', 'nonces', 'pending-nonces']
        # remove_fixture_directories(self.fixture_directories)
        create_fixture_directories(self.fixture_directories)

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.networks = []
        self.nodes = []
        self.processes = []
        self.logs = []
        self.parent_connections = []
        self.child_connections = []
        self.node_wallets = []

        self.founder_wallet = TEST_FOUNDATION_WALLET
        print("\n")

    def tearDown(self):
        for network in self.networks:
                network.stop()

        for process in self.processes:
                try:
                    process.terminate()
                except Exception:
                    pass

        for node in self.nodes:
            node.stop()

        self.ctx.destroy()
        self.loop.close()

        remove_fixture_directories(self.fixture_directories)

    def await_async_process(self, process, args={}):
        tasks = asyncio.gather(
            process(**args)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def await_block_process(self, block_num):
        tasks = asyncio.gather(
            self.wait_for_block(block_num=block_num)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    async def wait_for_block(self, block_num):
        nodes_current_blocks = {}

        def send_messages(parent_connections, processes):
            for index, process in enumerate(processes):
                parent_connections[index].send(["current_height", None])

        def get_messages(parent_connections, processes):
            for index, process in enumerate(processes):
                try:
                    msg = parent_connections[index].recv()
                except Exception as err:
                    print(err)

                action, current_height, node_vk = msg
                print(msg)
                if action == "current_height":
                    nodes_current_blocks[node_vk] = current_height

        def all_nodes_done():
            done = True
            for node in nodes_current_blocks:
                if nodes_current_blocks[node] != block_num:
                    done = False
            return done

        while True:
            send_messages(parent_connections=self.parent_connections, processes=self.processes)
            get_messages(parent_connections=self.parent_connections, processes=self.processes)
            if all_nodes_done():
                break

            self.async_sleep(1)

    async def check_for_all_started(self):
        nodes_started = {}

        def get_messages(parent_connections, processes):
            for index, process in enumerate(processes):
                try:
                    msg = parent_connections[index].recv()
                except Exception as err:
                    print(err)

                if msg:
                    action, payload = msg
                    self.logs.append(f'NODE {index}: {action} {payload}')
                    print(f'NODE {index}: {action} {payload}')
                    if action == "STARTED":
                        nodes_started[index] = payload

        while True:
            get_messages(parent_connections=self.parent_connections, processes=self.processes)
            if len(nodes_started) == len(self.processes):
                break
            self.async_sleep(1)

    async def stop_all_nodes(self):
        nodes_done = {}

        def send_messages(parent_connections, processes):
            for index, process in enumerate(processes):
                if nodes_done.get(index) is None:
                    parent_connections[index].send(["STOP", None])

        def get_messages(parent_connections, processes):
            for index, process in enumerate(processes):
                try:
                    msg = parent_connections[index].recv()
                except Exception as err:
                    print(err)

                if msg:
                    action, payload = msg
                    self.logs.append(f'NODE {index}: {action} {payload}')
                    print(f'NODE {index}: {action} {payload}')
                    if action == "STOPPED" and payload == True:
                        nodes_done[index] = payload

        send_messages(parent_connections=self.parent_connections, processes=self.processes)

        while True:
            get_messages(parent_connections=self.parent_connections, processes=self.processes)
            if len(nodes_done) == len(self.processes):
                break
            self.async_sleep(1)

    def send_tx(self, parent_connection, sender_wallet=None):
        parent_connection.send(["send_tx", {
            'sender_wallet': sender_wallet or self.founder_wallet
        }])

    def test_multip(self):
        constitution = {
            'masternodes': [],
            'delegates': []
        }

        bootnodes = {}


        try:
            node = MockMaster(index=0, conn=None, wallet=Wallet)
            node.set_start_variables(bootnodes=bootnodes, constitution=constitution)
            node.start()
        except Exception as err:
            print(err)

        def make_node(index, bootnodes, constitution, cconn):
            node = MockMaster(index=index, conn=cconn, wallet=self.node_wallets[index])
            node.set_start_variables(bootnodes=bootnodes, constitution=constitution)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tasks = asyncio.gather(
                node.start()
            )
            loop = asyncio.get_event_loop()
            loop.run_until_complete(tasks)


        for i in range(2):
            node_wallet = Wallet()
            parent_conn, child_conn = multiprocessing.Pipe()

            self.parent_connections.append(parent_conn)
            self.child_connections.append(child_conn)
            self.node_wallets.append(node_wallet)

            constitution['masternodes'].append(node_wallet.verifying_key)
            bootnodes[node_wallet.verifying_key] = f'tcp://127.0.0.1:{18000 + i}'

            p = Process(pn=i, cconn=self.child_connections[i], target=make_node, args=(i, bootnodes, constitution, self.child_connections[i]))
            self.processes.append(p)

        for index, process in enumerate(self.processes):
            process.start()

        self.await_async_process(self.check_for_all_started)

        # Send 5 transactions and wait for the nodes to increase block numbers
        for i in range(15):
            self.send_tx(parent_connection=self.parent_connections[i])
            self.await_block_process(block_num=i+1)
            self.async_sleep(0.1)

        self.await_async_process(self.stop_all_nodes)

        for index, process in enumerate(self.processes):
            self.child_connections[index].close()
            process.join()

        print(self.logs)
        self.assertTrue(True)

    def test_network(self):
        n = MockNetwork(num_of_masternodes=2, num_of_delegates=2)
        self.await_async_process(n.start)
        self.await_async_process(n.await_all_started)

        self.assertTrue(n.masternodes[0].started)

        self.await_async_process(n.stop)

    def test_node(self):
        node_wallet = Wallet()
        constitution = {
            'masternodes': [node_wallet.verifying_key],
            'delegates': []
        }
        bootnodes = {}
        bootnodes[node_wallet.verifying_key] = f'tcp://127.0.0.1:18000'

        node = MockMaster(index=0, wallet=node_wallet)
        node.set_start_variables(bootnodes=bootnodes, constitution=constitution)

        self.await_async_process(node.start)

    def test_process_communication_basic(self):

        def func_1(child_conn):
            async def receiver(child_conn):
                while True:
                    if child_conn.poll():
                        msg = child_conn.recv()
                        if msg == "ping":
                            child_conn.send("pong")

                    await asyncio.sleep(0)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tasks = asyncio.gather(
                receiver(child_conn=child_conn)
            )
            loop.run_until_complete(tasks)

        parent_conn, child_conn = multiprocessing.Pipe()
        p = Process(pn=0, cconn=child_conn, target=func_1, args=[child_conn])
        p.start()

        log = []

        async def parent_receiver(parent_conn, log):
            while True:
                if parent_conn.poll():
                    msg = parent_conn.recv()
                    if msg == "pong":
                        log.append(msg)

                await asyncio.sleep(0)

        asyncio.ensure_future(parent_receiver(parent_conn=parent_conn, log=log))

        while len(log) < 10:
            parent_conn.send("ping")
            self.async_sleep(0.1)

        p.terminate()

        self.assertTrue(len(log) >= 10)

    def test_node_in_process(self):
        def make_node(index, bootnodes, constitution, child_conn, node_wallet):
            async def receiver(child_conn, node):
                while True:
                    if child_conn.poll():
                        msg = child_conn.recv()
                        action, payload = msg
                        if action == "node_running":
                            if node.obj is None:
                                child_conn.send(["node_running", False])
                            else:
                                child_conn.send(["node_running", node.obj.running])

                    await asyncio.sleep(0)

            node = MockMaster(index=index, conn=child_conn, wallet=node_wallet)
            node.set_start_variables(bootnodes=bootnodes, constitution=constitution)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tasks = asyncio.gather(
                node.start()
            )
            loop.run_until_complete(tasks)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tasks = asyncio.gather(
                receiver(child_conn=child_conn, node=node)
            )
            loop.run_until_complete(tasks)


        node_wallet = Wallet()
        parent_conn, child_conn = multiprocessing.Pipe()

        constitution = {
            'masternodes': [node_wallet.verifying_key],
            'delegates': []
        }
        bootnodes = {}
        bootnodes[node_wallet.verifying_key] = f'tcp://127.0.0.1:18000'

        p = Process(pn=0, cconn=child_conn, target=make_node,
                    args=(0, bootnodes, constitution, child_conn, node_wallet))

        p.start()

        log = []

        async def parent_receiver(parent_conn):
            while True:
                if parent_conn.poll():
                    msg = parent_conn.recv()
                    action, payload = msg
                    if action == "node_running":
                        p.node_started = payload
                        log.append(payload)

                await asyncio.sleep(0)

        asyncio.ensure_future(parent_receiver(parent_conn=parent_conn))

        while not p.node_started:
            parent_conn.send(['node_running', None])
            self.async_sleep(0.5)

        p.terminate()

        self.assertTrue(p.node_started)

'''
    def test_network_can_propagate_transactions(self):
        # Test that the network can receive a transaction and send it around to all the other nodes

        # Create a network
        network_1 = MockNetwork(
            num_of_delegates=3,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )
        self.networks.append(network_1)
        self.await_async_process(network_1.start)

        # get a masternode
        masternode_1 = network_1.masternodes[0]

        receiver_wallet = Wallet()
        amount = 100.5

        # create a masternode
        tx = transaction.build_transaction(
            wallet=masternode_1.wallet,
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': amount}
            },
            stamps=100,
            processor=masternode_1.wallet.verifying_key,
            nonce=1
        )
        # Give the masternode the transaction
        masternode_1.tx_queue.append(tx.encode())

        # Wait for propagation around network
        self.async_sleep(1)

        # Check that each node ran the transaction
        all_nodes = network_1.all_nodes()
        for node in all_nodes:
            self.assertEqual(masternode_1.obj.last_processed_hlc, node.obj.last_processed_hlc)

    def test_network_can_propagate_results(self):
        # Test that the network can receive a transaction and send it around to all the other nodes

        # Create a network
        network_1 = MockNetwork(
            num_of_delegates=3,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )
        self.networks.append(network_1)
        self.await_async_process(network_1.start)

        # stop all nodes validation queues so that they collect all results and don't do consensus
        all_nodes = network_1.all_nodes()
        for node in all_nodes:
            node.obj.validation_queue.stop()

        # get a masternode
        masternode_1 = network_1.masternodes[0]

        receiver_wallet = Wallet()
        amount = 100.5

        # create a masternode
        tx = transaction.build_transaction(
            wallet=masternode_1.wallet,
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': amount}
            },
            stamps=100,
            processor=masternode_1.wallet.verifying_key,
            nonce=1
        )
        # Give the masternode the transaction
        masternode_1.tx_queue.append(tx.encode())

        # Wait for propagation around network
        self.async_sleep(1)

        hlc_timestamp = masternode_1.obj.last_processed_hlc
        all_solutions = masternode_1.obj.validation_queue.validation_results[hlc_timestamp]['solutions']

        # Check that each node ran the transaction
        for node in all_nodes:
            self.assertIsNotNone(all_solutions[node.wallet.verifying_key])
'''
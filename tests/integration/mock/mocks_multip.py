from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction
from contracting.db.driver import ContractDriver, Driver, InMemDriver
from contracting.db import encoder
from lamden import storage
from lamden.nodes import masternode, delegate, filequeue
import asyncio
import random
import httpx
from lamden.logger.base import get_logger
import json
import os
import shutil
import time
import pathlib
import zmq.asyncio

import multiprocessing
import traceback

MOCK_FOUNDER_SK = '016afd234c03229b44cfb3a067aa6d9ec3cd050774c6eff73aeb0b40cc8e3a12'

TEST_FOUNDATION_WALLET = Wallet(MOCK_FOUNDER_SK)

def await_all_nodes_done_processing(nodes, block_height, timeout, sleep=10):
    async def check():
        start = time.time()
        done = False
        while not done:
            await asyncio.sleep(sleep)
            heights = [node.obj.get_current_height() for node in nodes]
            results = [node.obj.get_current_height() == block_height for node in nodes]
            done = all(results)
            if not done:
                pass
            if timeout > 0 and time.time() - start > timeout:
                print([node.obj.get_current_height() == block_height for node in nodes])
                print({'heights':heights})
                print(f"HIT TIMER and {done}")
                done = True

    tasks = asyncio.gather(
        check()
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(tasks)

def create_fixture_directories(dir_list):
    for d in dir_list:
        try:
            pathlib.Path(f'./fixtures/{d}').mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            pass

def remove_fixture_directories(dir_list):
    for d in dir_list:
        try:
            shutil.rmtree(f'./fixtures/{d}')
        except Exception as err:
            print(err)
            pass

class Process(multiprocessing.Process):
    def __init__(self, index, child_conn, *args, **kwargs):
        multiprocessing.Process.__init__(self, *args, **kwargs)
        self.index = index
        self.child_conn = child_conn

    def run(self):
        try:
            multiprocessing.Process.run(self)
        except Exception as e:
            tb = traceback.format_exc()
            print (f'NODE {self.index}:\n', e, tb)
            self.child_conn.send(["NODE_ERROR"], (f'NODE {self.index}:\n', e, tb))


def process_target(NodeClass, index, child_conn, wallet, bootnodes, constitution):
    node = NodeClass(index=index, wallet=wallet)
    node.set_start_variables(bootnodes=bootnodes, constitution=constitution)

    async def child_message_receiver():
        while True:
            if child_conn.poll():
                msg = child_conn.recv()
                print(f'NODE CHILD {index}:', msg)
                action, payload = msg

                if action == "STOP":
                    await node.obj.stop()
                    child_conn.send(["node_running", node.obj.running])

                if action == "node_running":
                    if node.obj is None:
                        child_conn.send(["node_running", False])
                    else:
                        child_conn.send(["node_running", node.obj.running])

                if action == "node_type":
                    child_conn.send(["node_type", node.obj.upgrade_manager.node_type])

                if action == "get_file_queue_length":
                    child_conn.send(["get_file_queue_length", len(node.obj.tx_queue)])

                if action == "send_tx":
                    node.obj.tx_queue.append(payload)


                if action == "get_block":
                    block = node.obj.blocks.get_block(v=payload)
                    if block is None:
                        block = {
                            'number': 0,
                            'hash': f'0' * 64
                        }
                    child_conn.send(["get_block", block])

                if action == "current_height":
                    current_height = node.obj.get_current_height()
                    child_conn.send(["current_height", current_height])

                if action == "get_last_processed_hlc":
                    last_processed = node.obj.last_processed_hlc
                    child_conn.send(["get_last_processed_hlc", last_processed])

            await asyncio.sleep(0)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = asyncio.gather(
        node.start()
    )
    loop.run_until_complete(tasks)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = asyncio.gather(
        child_message_receiver()
    )
    loop.run_until_complete(tasks)

class NodeProcess:
    def __init__(self, NodeClass, index, metering, delay):
        self.process = None
        self.NodeClass = NodeClass

        child_conn, parent_conn = multiprocessing.Pipe()
        self.parent_conn = parent_conn
        self.child_conn = child_conn

        self.index = index
        self.metering = metering
        self.delay = delay

        port = 18000 + index
        self.ip = '127.0.0.1'
        self.port = port
        self.tcp = f'tcp://{self.ip}:{self.port}'

        self.bootnodes = {}
        self.constitution = {}
        self.wallet = Wallet()

        self.started = False
        self.node_type = None
        self.last_processed_hlc = None
        self.file_queue_length = None

        self.exception = None

    def set_start_variables(self, bootnodes, constitution):
        self.bootnodes = bootnodes
        self.constitution = constitution

    def init_process(self):
        try:
            self.process = Process(
                index=self.index,
                child_conn=self.child_conn,
                target=process_target,
                args=[self.NodeClass, self.index, self.child_conn, self.wallet, self.bootnodes, self.constitution]
            )

            asyncio.ensure_future(self.parent_message_receiver())
        except Exception as err:
            print(err)

    def start_process(self):
        self.process.start()

    async def parent_message_receiver(self):
        while True:
            if self.parent_conn.poll():
                msg = self.parent_conn.recv()
                print(f'NODE PARENT {self.index}:', msg)
                action, payload = msg
                if action == "NODE_ERROR":
                    self.exception = payload

                if action == "node_running":
                    self.started = payload

                if action == "node_type":
                    self.node_type = payload

                if action == "get_file_queue_length":
                    self.file_queue_length = payload

                if action == "get_last_processed_hlc":
                    if payload == "":
                        self.last_processed_hlc = None
                    else:
                        self.last_processed_hlc = payload
            await asyncio.sleep(0)

    def send_transaction(self, tx):
        self.parent_conn.send(["send_tx", tx])

    async def get_last_processed_hlc(self):
        self.last_processed_hlc = None
        self.parent_conn.send(["get_last_processed_hlc", None])

        while self.last_processed_hlc is None:
            await asyncio.sleep(0)

        return self.last_processed_hlc

    async def await_get_file_queue_length(self):
        self.file_queue_length = None
        self.parent_conn.send(["get_file_queue_length", None])

        while self.file_queue_length is None:
            await asyncio.sleep(0)

        return self.file_queue_length


class MockNode:
    def __init__(self, wallet=None, index=1, delay=None, genesis_path=os.path.dirname(os.path.abspath(__file__))):

        self.process = None

        self.wallet = wallet or Wallet()
        self.index = index
        port = 18000 + index
        self.ip = '127.0.0.1'
        self.port = port
        self.http = f'http://{self.ip}:{self.port}'
        self.tcp = f'tcp://{self.ip}:{self.port}'
        self.delay = delay or {
            'base': 0.1,
            'self': 0.2
        }

        self.driver = ContractDriver(driver=InMemDriver())
        self.driver.flush()

        self.nonces = storage.NonceStorage(
            nonce_collection=f'./fixtures/nonces/{self.wallet.verifying_key}',
            pending_collection=f'./fixtures/pending-nonces/{self.wallet.verifying_key}'
        )
        self.nonces.flush()

        self.bootnodes = {}
        self.constitution = {}
        self.ready_to_start = False

        self.started = False

        self.obj = None
        self.genesis_path = genesis_path

    def set_start_variables(self, bootnodes, constitution):
        self.bootnodes = bootnodes
        self.constitution = constitution
        self.ready_to_start = True

    def flush(self):
        self.driver.flush()
        self.nonces.flush()

    async def stop(self):
        await self.obj.stop()
        self.started = False

class MockMaster(MockNode):
    def __init__(self, conn=None, tx_queue=None, index=1, metering=False, wallet=None, delay=None):
        super().__init__(index=index, wallet=wallet, delay=delay)

        self.webserver_port = 18080 + index
        self.webserver_ip = f'http://0.0.0.0:{self.webserver_port}'
        self.metering = metering
        self.tx_queue = tx_queue or filequeue.FileQueue(root="./fixtures/file_queue/" + self.wallet.verifying_key + '/txq')
        self.conn = conn
        self.node_num = index

        self.founder_wallet = TEST_FOUNDATION_WALLET

    async def start(self):
        assert self.ready_to_start, 'Not ready to start!'

        self.obj = masternode.Masternode(
            testing=True,
            socket_base=self.tcp,
            wallet=self.wallet,
            constitution=self.constitution,
            bootnodes=self.bootnodes,
            driver=self.driver,
            tx_queue=self.tx_queue,
            webserver_port=self.webserver_port,
            genesis_path=self.genesis_path,
            nonces=self.nonces,
            metering=self.metering,
            delay=self.delay,
            blocks=storage.BlockStorage(root='./fixtures/block_storage/' + self.wallet.verifying_key)
        )

        await self.obj.start()
        self.started = True

class MockDelegate(MockNode):
    def __init__(self, index=1, wallet=None, metering=True, delay=None):
        super().__init__(index=index, wallet=wallet, delay=delay)

        self.metering = metering

    async def start(self):
        assert self.ready_to_start, 'Not ready to start!'

        self.obj = delegate.Delegate(
            testing=True,
            socket_base=self.tcp,
            wallet=self.wallet,
            constitution=self.constitution,
            bootnodes=self.bootnodes,
            driver=self.driver,
            genesis_path=self.genesis_path,
            nonces=self.nonces,
            metering=self.metering,
            delay=self.delay
        )

        await self.obj.start()
        self.started = True


class MockNetwork:
    def __init__(self, num_of_masternodes, num_of_delegates, metering=True, delay=None):
        self.masternodes = []
        self.delegates = []
        self.metering = metering

        self.log = get_logger('MOCKNET')

        self.delay = delay

        for i in range(0, num_of_masternodes):
            self.build_masternode(i)

        for i in range(num_of_masternodes, num_of_delegates + num_of_masternodes):
            self.build_delegate(i)

        self.constitution = None
        self.bootnodes = None

        self.prepare_nodes_to_start()

    def all_nodes(self):
        return self.masternodes + self.delegates

    def prepare_nodes_to_start(self):
        constitution = {
            'masternodes': [],
            'delegates': []
        }

        bootnodes = dict()

        for m in self.masternodes:
            constitution['masternodes'].append(m.wallet.verifying_key)
            bootnodes[m.wallet.verifying_key] = m.tcp

        for d in self.delegates:
            constitution['delegates'].append(d.wallet.verifying_key)
            bootnodes[d.wallet.verifying_key] = d.tcp

        for node_process in self.all_nodes():
            node_process.set_start_variables(bootnodes=bootnodes, constitution=constitution)

        self.constitution = constitution
        self.bootnodes = bootnodes

    def build_delegate(self, index):
        self.delegates.append(NodeProcess(
            NodeClass=MockDelegate,
            index=index,
            metering=self.metering,
            delay=self.delay
        ))

    def build_masternode(self, index):
        self.masternodes.append(NodeProcess(
            NodeClass=MockMaster,
            index=index,
            metering=self.metering,
            delay=self.delay
        ))

    async def fund(self, vk, amount=1_000_000):
        await self.make_and_push_tx(
            wallet=TEST_FOUNDATION_WALLET,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': amount,
                'to': vk
            }
        )

        await asyncio.sleep(4)

    def get_vars(self, contract, variable, arguments):
        values = []
        for node in self.all_nodes():
            val = node.obj.executor.driver.get_var(
                contract=contract,
                variable=variable,
                arguments=arguments,
                mark=False
            )

            values.append(json.loads(encoder.encode(val)))

        return values

    def get_var_from_one(self, contract, variable, arguments, node):
        return node.driver.get_var(
            contract=contract,
            variable=variable,
            arguments=arguments
        )

    def get_var_from_all(self, contract, variable, arguments):
        return [self.get_var_from_one(contract, variable, arguments, node) for node in self.all_nodes()]

    def set_var(self, contract, variable, arguments, value):
        for node_process in self.all_nodes():
            assert node_process.process.started, 'All nodes must be started first to mint.'

            node_process.driver.set_var(
                contract=contract,
                variable=variable,
                arguments=arguments,
                value=value
            )

    async def start(self):
        for node_process in self.all_nodes():
            try:
                node_process.init_process()
                node_process.start_process()
            except Exception as err:
                print(err)

    async def stop(self):
        all_node_processes = self.all_nodes()

        for node_process in all_node_processes:
            node_process.parent_conn.send(["STOP", None])

        for node_process in all_node_processes:
            while node_process.started:
                node_process.parent_conn.send(["node_running", None])
                await asyncio.sleep(0.1)

        for node_process in all_node_processes:
            node_process.child_conn.close()
            node_process.parent_conn.close()
            node_process.process.terminate()

    async def await_all_started(self):
        all_node_processes = self.all_nodes()

        all_started = False
        while not all_started:
            done = True
            self.check_all_started()
            for node_process in all_node_processes:
                if not node_process.started:
                    done = False
            all_started = done
            await asyncio.sleep(0.5)

    def check_all_started(self):
        for node_process in self.all_nodes():
            node_process.parent_conn.send(["node_running", None])

    async def await_get_all_node_types(self):
        for node_process in self.all_nodes():
            node_process.node_type = None
            node_process.parent_conn.send(["node_type", None])

        done = False
        while not done:
            got_all = True
            for node_process in self.all_nodes():
                if node_process.node_type == None:
                    got_all = False
            done = got_all
            await asyncio.sleep(0)

    def send_currency_transaction(self, sender_wallet=None, receiver_wallet=None, node_process=None, amount=None):
        if node_process is None:
            node_process = random.choice(self.masternodes)

        receiver_wallet = receiver_wallet or Wallet()
        amount = amount or str(round(random.uniform(1, 200), 4))

        tx = transaction.build_transaction(
            wallet=sender_wallet or Wallet(),
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': amount}
            },
            stamps=100,
            processor=node_process.wallet.verifying_key,
            nonce=1
        )
        node_process.send_transaction(tx=tx.encode())

        return (node_process, tx)


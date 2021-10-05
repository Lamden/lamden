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

                if action == "send_tx":
                    sender_wallet = payload.get('sender_wallet')
                    receiver_wallet = payload.get('receiver_wallet')

                    receiver_wallet = receiver_wallet or Wallet()
                    amount = str(round(random.uniform(1, 200), 4))

                    tx = transaction.build_transaction(
                        wallet=sender_wallet,
                        contract='currency',
                        function='transfer',
                        kwargs={
                            'to': receiver_wallet.verifying_key,
                            'amount': {'__fixed__': amount}
                        },
                        stamps=100,
                        processor=node.obj.wallet.verifying_key,
                        nonce=1
                    )
                    node.obj.tx_queue.append(tx.encode())

                if action == "get_block":
                    block = node.obj.blocks.get_block(v=payload)
                    if block is None:
                        block = {
                            'number': 0,
                            'hash': f'0' * 64
                        }
                    child_conn.send(["get_block", block, node.obj.wallet.verifying_key])

                if action == "current_height":
                    current_height = node.obj.get_current_height()
                    child_conn.send(["current_height", current_height, node.obj.wallet.verifying_key])

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

        self.exception = None

    def set_start_variables(self, bootnodes, constitution):
        self.bootnodes = bootnodes
        self.constitution = constitution

    def init_process(self):
        print("called")
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
            await asyncio.sleep(0)

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
            blocks=storage.BlockStorage(home='./fixtures/block_storage/' + self.wallet.verifying_key)
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

        for node_process in self.masternodes + self.delegates:
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
        for node in self.masternodes + self.delegates:
            assert node.started, 'All nodes must be started first to mint.'

            node.driver.set_var(
                contract=contract,
                variable=variable,
                arguments=arguments,
                value=value
            )

    async def start(self):
        print(self.masternodes + self.delegates)
        for node_process in self.masternodes + self.delegates:
            print(node_process)
            try:
                node_process.init_process()
                node_process.start_process()
            except Exception as err:
                print(err)

    async def stop(self):
        for node_process in self.masternodes + self.delegates:
            node_process.parent_conn.send(["STOP", None])

        for node_process in self.masternodes + self.delegates:
            while node_process.started:
                node_process.parent_conn.send(["node_running", None])
                await asyncio.sleep(0.1)

        for node_process in self.masternodes + self.delegates:
            node_process.child_conn.close()
            node_process.parent_conn.close()
            node_process.process.terminate()

    async def await_all_started(self):
        all_started = False
        while not all_started:
            done = True
            self.check_all_started()
            for node_process in self.masternodes + self.delegates:
                if not node_process.started:
                    done = False
            all_started = done
            await asyncio.sleep(0.5)

    def check_all_started(self):
        for node_process in self.masternodes + self.delegates:
            node_process.parent_conn.send(["node_running", None])

    async def push_tx(self, node, wallet, contract, function, kwargs, stamps, nonce):
        tx = transaction.build_transaction(
            wallet=wallet,
            contract=contract,
            function=function,
            kwargs=kwargs,
            stamps=stamps,
            processor=node.wallet.verifying_key,
            nonce=nonce
        )

        async with httpx.AsyncClient() as client:
            await client.post(f'{node.webserver_ip}/', data=tx)

    async def push_tx_to_tx_queue(self, node=None, wallet=None, contract=None, function=None, kwargs=None, stamps=None, nonce=None, tx_info=None):
        tx = tx_info or transaction.build_transaction(
            wallet=wallet,
            contract=contract,
            function=function,
            kwargs=kwargs,
            stamps=stamps,
            processor=node.wallet.verifying_key,
            nonce=nonce
        )

        node.obj.tx_queue.append(tx)

    def send_random_currency_transaction(self, sender_wallet, receiver_wallet=None):
        node = random.choice(self.masternodes)

        receiver_wallet = receiver_wallet or Wallet()
        amount = str(round(random.uniform(1, 200), 4))

        tx = transaction.build_transaction(
            wallet=sender_wallet,
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': amount}
            },
            stamps=100,
            processor=node.wallet.verifying_key,
            nonce=1
        )
        node.tx_queue.append(tx.encode())
        return tx

    async def make_and_push_tx(self, wallet, contract, function, kwargs={}, stamps=1_000_000, mn_idx=0, random_select=False):
        # Mint money if we have to
        # Get our node we are going to send the tx to
        if random_select:
            node = random.choice(self.masternodes)
        else:
            node = self.masternodes[mn_idx]

        processor = node.wallet.verifying_key

        async with httpx.AsyncClient() as client:
            response = await client.get(f'{node.webserver_ip}/nonce/{wallet.verifying_key}')
            nonce = response.json()['nonce']

        self.log.info(f'Nonce is {nonce}')

        await self.push_tx(
            node=node,
            wallet=wallet,
            contract=contract,
            function=function,
            kwargs=kwargs,
            stamps=stamps,
            nonce=nonce
        )

    def flush(self):
        for node in self.masternodes + self.delegates:
            node.flush()

    def refresh(self):
        self.flush()
        for node in self.masternodes + self.delegates:
            node.obj.seed_genesis_contracts()

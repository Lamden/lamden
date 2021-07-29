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

MOCK_FOUNDER_SK = '016afd234c03229b44cfb3a067aa6d9ec3cd050774c6eff73aeb0b40cc8e3a12'

TEST_FOUNDATION_WALLET = Wallet(MOCK_FOUNDER_SK)


def await_all_nodes_done_processing(nodes, block_height, timeout):
    async def check():
        start = time.time()
        done = False
        while not done:
            done = all([node.obj.get_current_height() == block_height for node in nodes])
            await asyncio.sleep(0.0)
            if time.time() - start > timeout:
                print([node.obj.get_current_height() == block_height for node in nodes])
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
        except Exception:
            pass

class MockNode:
    def __init__(self, ctx,  wallet=None, index=1, genesis_path=os.path.dirname(os.path.abspath(__file__))):
        self.wallet = wallet or Wallet()
        self.index = index
        port = 18000 + index
        self.ip = '127.0.0.1'
        self.port = port
        self.http = f'http://{self.ip}:{self.port}'
        self.tcp = f'tcp://{self.ip}:{self.port}'
        self.delay = {
            'base': 5,
            'self': 2
        }

        self.driver = ContractDriver(driver=InMemDriver())
        self.driver.flush()

        self.nonces = storage.NonceStorage(
            nonce_collection=f'./fixtures/nonces/{self.wallet.verifying_key}',
            pending_collection=f'./fixtures/pending-nonces/{self.wallet.verifying_key}'
        )
        self.nonces.flush()

        self.ctx = ctx

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


class MockMaster(MockNode):
    def __init__(self, ctx, tx_queue=None, index=1, metering=True, wallet=None):
        super().__init__(ctx=ctx, index=index, wallet=wallet)

        self.webserver_port = 18080 + index
        self.webserver_ip = f'http://0.0.0.0:{self.webserver_port}'
        self.metering = metering
        self.tx_queue = tx_queue or filequeue.FileQueue(root="./fixtures/file_queue/" + self.wallet.verifying_key + '/txq')

    async def start(self):
        assert self.ready_to_start, 'Not ready to start!'

        self.obj = masternode.Masternode(
            socket_base=self.tcp,
            ctx=self.ctx,
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

    def stop(self):
        self.obj.stop()

class MockDelegate(MockNode):
    def __init__(self, ctx, index=1, wallet=None, metering=True):
        super().__init__(ctx=ctx, index=index, wallet=wallet)

        self.metering = metering

    async def start(self):
        assert self.ready_to_start, 'Not ready to start!'

        self.obj = delegate.Delegate(
            socket_base=self.tcp,
            ctx=self.ctx,
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

    def stop(self):
        self.obj.stop()


class MockNetwork:
    def __init__(self, num_of_masternodes, num_of_delegates, ctx, metering=True):
        self.masternodes = []
        self.delegates = []
        self.metering = metering

        self.log = get_logger('MOCKNET')

        self.ctx = ctx

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

        for node in self.masternodes + self.delegates:
            node.set_start_variables(bootnodes=bootnodes, constitution=constitution)

        self.constitution = constitution
        self.bootnodes = bootnodes

    def build_delegate(self, index):
        self.delegates.append(MockDelegate(ctx=self.ctx, index=index, metering=self.metering))

    def build_masternode(self, index):
        self.masternodes.append(MockMaster(ctx=self.ctx, index=index, metering=self.metering))

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

    def get_var(self, contract, variable, arguments, delegates=False):
        true_value = None
        for master in self.masternodes:
            value = master.driver.get_var(
                contract=contract,
                variable=variable,
                arguments=arguments
            )
            if true_value is None:
                true_value = value
            else:
                assert true_value == value, 'Masters have inconsistent state!'

        if delegates:
            for delegate in self.delegates:
                value = delegate.driver.get_var(
                    contract=contract,
                    variable=variable,
                    arguments=arguments
                )
                if true_value is None:
                    true_value = value
                else:
                    assert true_value == value, 'Masters have inconsistent state!'

        return true_value

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
        coroutines = [node.start() for node in self.masternodes + self.delegates]

        await asyncio.gather(
            *coroutines
        )

    def stop(self):
        for node in self.masternodes + self.delegates:
            node.stop()

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

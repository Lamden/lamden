from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction
from contracting.db.driver import ContractDriver, Driver, InMemDriver, FSDriver
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
from pathlib import Path

MOCK_FOUNDER_SK = '016afd234c03229b44cfb3a067aa6d9ec3cd050774c6eff73aeb0b40cc8e3a12'


def await_all_nodes_done_processing(nodes, block_height, timeout, sleep=10):
    async def check():
        start = time.time()
        done = False
        while not done:
            await asyncio.sleep(sleep)
            heights = [node.obj.get_current_height() for node in nodes]
            results = [node.obj.get_current_height() == block_height for node in nodes]
            done = all(results)

            if done and block_height == 25:
                print('Done')

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


class MockNode:
    def __init__(self, ctx,  wallet=None, index=1, delay=None, genesis_path=os.path.dirname(os.path.abspath(__file__))):
        self.wallet = wallet or Wallet()
        self.index = index
        self.socket_ports = {
            'router': 19000 + self.index,
            'publisher': 19080 + self.index,
            'webserver': 18080 + self.index
        }
        self.ip = '127.0.0.1'
        self.tcp = f'tcp://{self.ip}'
        self.http = f'http://{self.ip}:{self.socket_ports.get("webserver")}'
        self.delay = delay or {
            'base': 0.1,
            'self': 0.2
        }

        self.current_path = Path.cwd()

        self.block_storage_path = Path(f'{self.current_path}/fixtures/block_storage/{self.wallet.verifying_key}')

        self.driver = ContractDriver(driver=InMemDriver())
        self.driver.flush()

        self.nonces = storage.NonceStorage(
            nonce_collection=f'{self.current_path}/fixtures/nonces/{self.wallet.verifying_key}',
            pending_collection=f'{self.current_path}/fixtures/pending-nonces/{self.wallet.verifying_key}'
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
    def __init__(self, ctx, tx_queue=None, index=1, metering=True, wallet=None, delay=None):
        super().__init__(ctx=ctx, index=index, wallet=wallet, delay=delay)

        self.webserver_port = 18080 + index
        self.webserver_ip = f'http://0.0.0.0:{self.webserver_port}'
        self.metering = metering
        self.tx_queue = tx_queue or filequeue.FileQueue(root=f'{self.current_path}/fixtures/file_queue/{self.wallet.verifying_key}/txq')

    async def start(self):
        assert self.ready_to_start, 'Not ready to start!'

        self.obj = masternode.Masternode(
            testing=True,
            ctx=self.ctx,
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
            blocks=storage.BlockStorage(home=self.block_storage_path)
        )

        self.obj.network.socket_ports = self.socket_ports
        self.obj.network.router.address = self.obj.network.router_address
        self.obj.network.publisher.address = self.obj.network.publisher_address

        await self.obj.start()

        self.started = True

    async def stop(self):
        await self.obj.stop()


class MockDelegate(MockNode):
    def __init__(self, ctx, index=1, wallet=None, metering=True, delay=None):
        super().__init__(ctx=ctx, index=index, wallet=wallet, delay=delay)

        self.metering = metering

    async def start(self):
        assert self.ready_to_start, 'Not ready to start!'

        self.obj = delegate.Delegate(
            testing=True,
            socket_base=self.tcp,
            ctx=self.ctx,
            wallet=self.wallet,
            constitution=self.constitution,
            bootnodes=self.bootnodes,
            driver=self.driver,
            genesis_path=self.genesis_path,
            nonces=self.nonces,
            metering=self.metering,
            delay=self.delay,
            blocks=storage.BlockStorage(home=self.block_storage_path)
        )

        self.obj.network.socket_ports = self.socket_ports
        self.obj.network.router.address = self.obj.network.router_address
        self.obj.network.publisher.address = self.obj.network.publisher_address

        await self.obj.start()
        self.started = True

    async def stop(self):
        await self.obj.stop()


class MockNetwork:
    def __init__(self, num_of_masternodes, num_of_delegates, ctx, metering=True, delay=None, index=0):
        self.masternodes = []
        self.delegates = []
        self.metering = metering

        self.log = get_logger('MOCKNET')

        self.ctx = ctx

        self.delay = delay

        self.founder_wallet = Wallet(MOCK_FOUNDER_SK)

        self.fixtures_dir = Path(f'{Path.cwd()}/fixtures')
        self.clean_fixtures_dir()

        for i in range(index, index + num_of_masternodes):
            self.build_masternode(i)

        for i in range(index + num_of_masternodes, index + num_of_delegates + num_of_masternodes):
            self.build_delegate(i)

        self.constitution = None
        self.bootnodes = None


        self.prepare_nodes_to_start()

    def clean_fixtures_dir(self):
        shutil.rmtree(self.fixtures_dir)

    def all_nodes(self):
        return self.masternodes + self.delegates
    @property
    def nodes(self):
        return self.masternodes + self.delegates

    def prepare_nodes_to_start(self):
        constitution = {
            'masternodes': [],
            'delegates': []
        }

        bootnodes = dict()

        for m in self.masternodes:
            constitution['masternodes'].append(m.wallet.verifying_key)
            bootnodes[m.wallet.verifying_key] = f'{m.tcp}:{m.socket_ports.get("router")}'

        for d in self.delegates:
            constitution['delegates'].append(d.wallet.verifying_key)
            bootnodes[d.wallet.verifying_key] = f'{d.tcp}:{d.socket_ports.get("router")}'

        for node in self.masternodes + self.delegates:
            node.set_start_variables(bootnodes=bootnodes, constitution=constitution)

        self.constitution = constitution
        self.bootnodes = bootnodes

    def build_delegate(self, index):
        self.delegates.append(MockDelegate(ctx=self.ctx, index=index, metering=self.metering, delay=self.delay))

    def build_masternode(self, index):
        self.masternodes.append(MockMaster(ctx=self.ctx, index=index, metering=self.metering, delay=self.delay))

    async def fund(self, vk, amount=1_000_000):
        await self.make_and_push_tx(
            wallet=self.founder_wallet,
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

    async def start_masters(self):
        coroutines = [node.start() for node in self.masternodes]

        await asyncio.gather(
            *coroutines
        )

    async def start_delegates(self):
        coroutines = [node.start() for node in self.delegates]

        await asyncio.gather(
            *coroutines
        )

    async def start(self):
        coroutines = [node.start() for node in self.masternodes + self.delegates]

        await asyncio.gather(
            *coroutines
        )

    async def stop(self):
        coroutines = [node.stop() for node in self.masternodes]

        await asyncio.gather(
            *coroutines
        )

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

    async def pause_all_queues(self):
        for node in self.nodes:
            await node.obj.pause_all_queues()

    async def pause_all_validation_queues(self):
        for node in self.nodes:
            node.obj.validation_queue.pause()
            await node.obj.validation_queue.pausing()

    def unpause_all_queues(self):
        for node in self.nodes:
            node.obj.unpause_all_queues()

    def unpause_all_main_processing_queues(self):
        for node in self.nodes:
            node.obj.main_processing_queue.unpause()

    def unpause_all_validation_queues(self):
        for node in self.nodes:
            node.obj.validation_queue.unpause()

    def flush(self):
        for node in self.nodes:
            node.flush()

    def refresh(self):
        self.flush()
        for node in self.nodes:
            node.obj.seed_genesis_contracts()

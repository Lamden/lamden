from cilantro.crypto import transaction
from cilantro.crypto.wallet import Wallet
from cilantro.crypto import canonical
from contracting.db.driver import decode, ContractDriver, InMemDriver
from contracting.client import ContractingClient
from cilantro.nodes import masternode, delegate
import zmq.asyncio
import asyncio

from unittest import TestCase
import httpx


def generate_blocks(number_of_blocks, subblocks=[]):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        if len(subblocks) > i:
            subblock = subblocks[i]
        else:
            subblock = []

        new_block = canonical.block_from_subblocks(
            subblocks=subblock,
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()




class TestFullFlow(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        self.driver = ContractDriver(driver=InMemDriver())
        self.client = ContractingClient(driver=self.driver)
        self.client.flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.client.flush()
        self.driver.flush()
        self.ctx.destroy()
        self.loop.close()

    def test_startup_network_and_process_single_tx_works(self):
        mw = Wallet()
        mip = 'tcp://127.0.0.1:18001'

        dw = Wallet()
        dip = 'tcp://127.0.0.1:18002'

        bootnodes = {
            mw.verifying_key: mip,
            dw.verifying_key: dip
        }

        constitution = {
            'masternodes': [mw.verifying_key],
            'delegates': [dw.verifying_key]
        }

        mnd = ContractDriver(driver=InMemDriver())
        mn = masternode.Masternode(
            socket_base=mip,
            ctx=self.ctx,
            wallet=mw,
            constitution=constitution,
            driver=mnd,
            bootnodes=bootnodes
        )

        dld = ContractDriver(driver=InMemDriver())
        dl = delegate.Delegate(
            socket_base=dip,
            ctx=self.ctx,
            wallet=dw,
            constitution=constitution,
            driver=dld,
            bootnodes=bootnodes
        )

        sender = Wallet()

        async def test():
            await asyncio.gather(
                mn.start(),
                dl.start()
            )

            mnd.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
            dld.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)

            tx = transaction.build_transaction(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': 'jeff'
                },
                stamps=5000,
                nonce=0,
                processor=mw.verifying_key
            )

            tx_decoded = decode(tx)
            mn.tx_batcher.queue.append(tx_decoded)

            await asyncio.sleep(2)

            mn.stop()
            dl.stop()

        self.loop.run_until_complete(test())

        # Delegates are 'behind' one step in state, so until the next block, they will not have processed these state changes
        #dbal = dld.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal = mnd.get_var(contract='currency', variable='balances', arguments=['jeff'])

        #self.assertEqual(dbal, 1338)
        self.assertEqual(mbal, 1338)

    def test_startup_network_and_process_single_tx_works_from_webserver(self):
        mw = Wallet()
        mip = 'tcp://127.0.0.1:18001'

        dw = Wallet()
        dip = 'tcp://127.0.0.1:18002'

        bootnodes = {
            mw.verifying_key: mip,
            dw.verifying_key: dip
        }

        constitution = {
            'masternodes': [mw.verifying_key],
            'delegates': [dw.verifying_key]
        }

        mnd = ContractDriver(driver=InMemDriver())
        mn = masternode.Masternode(
            socket_base=mip,
            ctx=self.ctx,
            wallet=mw,
            constitution=constitution,
            driver=mnd,
            bootnodes=bootnodes
        )

        dld = ContractDriver(driver=InMemDriver())
        dl = delegate.Delegate(
            socket_base=dip,
            ctx=self.ctx,
            wallet=dw,
            constitution=constitution,
            driver=dld,
            bootnodes=bootnodes
        )

        sender = Wallet()

        async def test():
            await asyncio.gather(
                mn.start(),
                dl.start()
            )

            mnd.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
            dld.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)

            tx = transaction.build_transaction(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': 'jeff'
                },
                stamps=5000,
                nonce=0,
                processor=mw.verifying_key
            )

            async with httpx.AsyncClient() as client:
                await client.post('http://0.0.0.0:8080/', data=tx)

            await asyncio.sleep(2)

            mn.stop()
            dl.stop()

        self.loop.run_until_complete(test())

        # dbal = dld.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal = mnd.get_var(contract='currency', variable='balances', arguments=['jeff'])

        # self.assertEqual(dbal, 1338)
        self.assertEqual(mbal, 1338)

    def test_startup_network_and_process_two_blocks_works_from_webserver(self):
        mw = Wallet()
        mip = 'tcp://127.0.0.1:18001'

        dw = Wallet()
        dip = 'tcp://127.0.0.1:18002'

        bootnodes = {
            mw.verifying_key: mip,
            dw.verifying_key: dip
        }

        constitution = {
            'masternodes': [mw.verifying_key],
            'delegates': [dw.verifying_key]
        }

        mnd = ContractDriver(driver=InMemDriver())
        mn = masternode.Masternode(
            socket_base=mip,
            ctx=self.ctx,
            wallet=mw,
            constitution=constitution,
            driver=mnd,
            bootnodes=bootnodes
        )

        dld = ContractDriver(driver=InMemDriver())
        dl = delegate.Delegate(
            socket_base=dip,
            ctx=self.ctx,
            wallet=dw,
            constitution=constitution,
            driver=dld,
            bootnodes=bootnodes
        )

        sender = Wallet()

        async def test():
            await asyncio.gather(
                mn.start(),
                dl.start()
            )

            mnd.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
            dld.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)

            tx = transaction.build_transaction(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': 'jeff'
                },
                stamps=5000,
                nonce=0,
                processor=mw.verifying_key
            )

            async with httpx.AsyncClient() as client:
                await client.post('http://0.0.0.0:8080/', data=tx)

            await asyncio.sleep(2)

            tx = transaction.build_transaction(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 444,
                    'to': 'stu'
                },
                stamps=5000,
                nonce=0,
                processor=mw.verifying_key
            )

            async with httpx.AsyncClient() as client:
                await client.post('http://0.0.0.0:8080/', data=tx)

            await asyncio.sleep(2)

            mn.stop()
            dl.stop()

        self.loop.run_until_complete(test())

        dbal = dld.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal = mnd.get_var(contract='currency', variable='balances', arguments=['jeff'])

        self.assertEqual(dbal, 1338)
        self.assertEqual(mbal, 1338)

        mbal = mnd.get_var(contract='currency', variable='balances', arguments=['stu'])

        self.assertEqual(mbal, 444)

    def test_two_masters_two_delegates_processes_two_blocks(self):
        mw1 = Wallet()
        mip1 = 'tcp://127.0.0.1:18001'
        mw2 = Wallet()
        mip2 = 'tcp://127.0.0.1:18002'

        dw1 = Wallet()
        dip1 = 'tcp://127.0.0.1:18003'
        dw2 = Wallet()
        dip2 = 'tcp://127.0.0.1:18004'

        bootnodes = {
            mw1.verifying_key: mip1,
            mw2.verifying_key: mip2,
            dw1.verifying_key: dip1,
            dw2.verifying_key: dip2
        }

        constitution = {
            'masternodes': [mw1.verifying_key, mw2.verifying_key],
            'delegates': [dw1.verifying_key, dw2.verifying_key]
        }

        mnd1 = ContractDriver(driver=InMemDriver())
        mn1 = masternode.Masternode(
            socket_base=mip1,
            ctx=self.ctx,
            wallet=mw1,
            constitution=constitution,
            driver=mnd1,
            bootnodes=bootnodes,
            webserver_port=8080
        )

        mnd2 = ContractDriver(driver=InMemDriver())
        mn2 = masternode.Masternode(
            socket_base=mip2,
            ctx=self.ctx,
            wallet=mw2,
            constitution=constitution,
            driver=mnd2,
            bootnodes=bootnodes,
            webserver_port=8081
        )

        dld1 = ContractDriver(driver=InMemDriver())
        dl1 = delegate.Delegate(
            socket_base=dip1,
            ctx=self.ctx,
            wallet=dw1,
            constitution=constitution,
            driver=dld1,
            bootnodes=bootnodes
        )

        dld2 = ContractDriver(driver=InMemDriver())
        dl2 = delegate.Delegate(
            socket_base=dip2,
            ctx=self.ctx,
            wallet=dw2,
            constitution=constitution,
            driver=dld2,
            bootnodes=bootnodes
        )

        sender = Wallet()

        async def test():
            await asyncio.gather(
                mn1.start(),
                mn2.start(),
                dl1.start(),
                dl2.start()
            )

            mnd1.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
            mnd2.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
            dld1.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
            dld2.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)

            tx = transaction.build_transaction(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': 'jeff'
                },
                stamps=5000,
                nonce=0,
                processor=mw1.verifying_key
            )

            async with httpx.AsyncClient() as client:
                await client.post('http://0.0.0.0:8080/', data=tx)

            await asyncio.sleep(2)

            tx = transaction.build_transaction(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 444,
                    'to': 'stu'
                },
                stamps=5000,
                nonce=0,
                processor=mw2.verifying_key
            )

            async with httpx.AsyncClient() as client:
                await client.post('http://0.0.0.0:8081/', data=tx)

            await asyncio.sleep(2)

            mn1.stop()
            mn2.stop()
            dl1.stop()
            dl2.stop()

        self.loop.run_until_complete(test())

        dbal1 = dld1.get_var(contract='currency', variable='balances', arguments=['jeff'])
        dbal2 = dld1.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal1 = mnd1.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal2 = mnd1.get_var(contract='currency', variable='balances', arguments=['jeff'])

        self.assertEqual(dbal1, 1338)
        self.assertEqual(dbal2, 1338)
        self.assertEqual(mbal1, 1338)
        self.assertEqual(mbal2, 1338)

        mbal1 = mnd1.get_var(contract='currency', variable='balances', arguments=['stu'])
        mbal2 = mnd2.get_var(contract='currency', variable='balances', arguments=['stu'])

        self.assertEqual(mbal1, 444)
        self.assertEqual(mbal2, 444)
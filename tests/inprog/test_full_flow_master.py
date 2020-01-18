from unittest import TestCase
import zmq.asyncio
import asyncio
from contracting.client import ContractingClient
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.messages import Message
from contracting import config
import os
import capnp
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
from cilantro_ee.crypto.transaction import TransactionBuilder
from contracting.db.driver import ContractDriver
import time

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

mnw1 = Wallet()

dw1 = Wallet()

constitution = {
    "masternodes": {
        "vk_list": [
            mnw1.verifying_key().hex(),
        ],
        "min_quorum": 1
    },
    "delegates": {
        "vk_list": [
            dw1.verifying_key().hex(),
        ],
        "min_quorum": 1
    },
    "witnesses": {},
    "schedulers": {},
    "notifiers": {},
    "enable_stamps": False,
    "enable_nonces": False
}


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


n1 = '/tmp/n1'
make_ipc(n1)


def make_tx(processor, contract_name, function_name, kwargs={}):
    w = Wallet()
    batch = TransactionBuilder(
        sender=w.verifying_key(),
        contract=contract_name,
        function=function_name,
        kwargs=kwargs,
        stamps=10000,
        processor=processor,
        nonce=0
    )

    batch.sign(w.signing_key())
    b = batch.serialize()

    tx = transaction_capnp.Transaction.from_bytes_packed(b)

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       w.verifying_key().hex())

    driver = ContractDriver()
    driver.set(balances_key, 1_000_000)
    driver.commit()

    return tx


class MockDelegate:
    def __init__(self, ctx, ipc='n1'):
        self.ctx = ctx

        self.delegate_work = self.ctx.socket(zmq.ROUTER)
        self.delegate_work.bind(f'ipc:///tmp/{ipc}/incoming_work')

        self.delegate_nbn = self.ctx.socket(zmq.ROUTER)
        self.delegate_nbn.bind(f'ipc:///tmp/{ipc}/block_notifications')

    async def recv_work(self):
        _id, msg = await self.delegate_work.recv_multipart()
        _, tx_batch, _, _, _ = Message.unpack_message_2(msg)
        return tx_batch


class TestMasterFullFlow(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        ContractingClient().flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_send_work_returns_none_if_no_one_online(self):
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        r = self.loop.run_until_complete(m.send_work())

        self.assertIsNone(r)

    def test_send_work_returns_sends_if_successful(self):
        make_ipc('/tmp/n2')
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n2',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        d = MockDelegate(self.ctx)

        m.parameters.sockets = {
            dw1.verifying_key().hex(): 'ipc:///tmp/n1'
        }

        tasks = asyncio.gather(
            m.send_work(),
            d.recv_work()
        )

        r, _ = self.loop.run_until_complete(tasks)

        status, socket = r[0]
        self.assertTrue(status)
        self.assertEqual(socket, 'ipc:///tmp/n1/incoming_work')

    def test_send_work_sends_tx_batch_properly(self):
        make_ipc('/tmp/n2')
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n2',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        d = MockDelegate(self.ctx)

        m.parameters.sockets = {
            dw1.verifying_key().hex(): 'ipc:///tmp/n1'
        }

        tasks = asyncio.gather(
            m.send_work(),
            d.recv_work()
        )

        tx = make_tx(mnw1.verifying_key().hex(),
                     contract_name='howdy',
                     function_name='yoohoo')

        m.tx_batcher.queue.append(tx)

        _, msg = self.loop.run_until_complete(tasks)

        self.assertEqual(msg.transactions[0].to_dict(), tx.to_dict())

    def test_wait_for_work_does_not_block_if_not_skip_block(self):
        make_ipc('/tmp/n2')
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n2',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        not_skip = {
            'subBlocks': []
        }

        async def wait_then_put_in_work():
            await asyncio.sleep(0.1)
            return time.time()

        async def wait_for_work_wrapped():
            await m.wait_for_work(not_skip)
            return time.time()

        tasks = asyncio.gather(
            wait_then_put_in_work(),
            wait_for_work_wrapped()
        )

        r, r2 = self.loop.run_until_complete(tasks)

        # Wait for work should finish after wait then put in work
        self.assertGreater(r, r2)

    def test_wait_for_work_blocks_if_skip_block_and_tx_batcher_empty(self):
        make_ipc('/tmp/n2')
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n2',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        skip = {
            'subBlocks': [
                {
                    'transactions': []
                }
            ]
        }

        async def wait_then_put_in_work():
            await asyncio.sleep(0.1)
            m.tx_batcher.queue.append(b'work')
            return time.time()

        async def wait_for_work_wrapped():
            await m.wait_for_work(skip)
            return time.time()

        tasks = asyncio.gather(
            wait_then_put_in_work(),
            wait_for_work_wrapped()
        )

        r, r2 = self.loop.run_until_complete(tasks)

        # Wait for work should finish after wait then put in work
        self.assertGreater(r2, r)

    def test_wait_for_work_does_not_block_if_skip_block_and_tx_batcher_not_empty(self):
        make_ipc('/tmp/n2')
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n2',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        skip = {
            'subBlocks': [
                {
                    'transactions': []
                }
            ]
        }

        m.tx_batcher.queue.append(b'work')

        async def wait_then_put_in_work():
            await asyncio.sleep(0.1)
            return time.time()

        async def wait_for_work_wrapped():
            await m.wait_for_work(skip)
            return time.time()

        tasks = asyncio.gather(
            wait_then_put_in_work(),
            wait_for_work_wrapped()
        )

        r, r2 = self.loop.run_until_complete(tasks)

        # Wait for work should finish after wait then put in work
        self.assertGreater(r, r2)

    def test_wait_for_work_deletes_all_old_nbns(self):
        pass

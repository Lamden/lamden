from unittest import TestCase
from cilantro_ee.nodes.delegate.delegate import Delegate

from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.core import canonical
from cilantro_ee.storage import MetaDataStorage

from contextlib import suppress
import zmq.asyncio
import asyncio

from contracting import config
import os
import capnp
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
from cilantro_ee.crypto.transaction import TransactionBuilder
from cilantro_ee.crypto.transaction_batch import transaction_list_to_transaction_batch

from cilantro_ee.messages import MessageType, Message
import struct

from contracting.db.driver import ContractDriver

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

mnw1 = Wallet()
mnw2 = Wallet()

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

n1 = '/tmp/n1'
n3 = '/tmp/n3'

def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


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

class ComplexMockMasternode:
    def __init__(self, ctx: zmq.asyncio.Context, delegate_work, delegate_nbn, wallet=Wallet(),
                 ipc='n2'):
        # Store delegate work socket
        # Store delegate nbn socket
        self.ctx = ctx

        self.delegate_work = self.ctx.socket(zmq.DEALER)
        self.delegate_work.connect(delegate_work)

        self.delegate_nbn = self.ctx.socket(zmq.DEALER)
        self.delegate_nbn.connect(delegate_nbn)

        make_ipc(f'/tmp/{ipc}')

        self.mn_agg = self.ctx.socket(zmq.ROUTER)
        self.mn_agg.bind(f'ipc:///tmp/{ipc}/block_aggregator')

        self.mn_nbn = self.ctx.socket(zmq.ROUTER)
        self.mn_nbn.bind(f'ipc:///tmp/{ipc}/block_notifications')

        self.wallet = wallet
        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=[])

    async def send_to_work_socket(self):
        await self.delegate_work.send(self.tx_batcher.pack_current_queue())

    async def send_new_block_to_socket(self, b=None):
        if b is None:
            b = canonical.get_genesis_block()

        await self.delegate_nbn.send(canonical.dict_to_msg_block(b))

    async def process_blocks(self):
        #
        # Send tx batch
        # Receive reply
        # Set reply to object?
        # Turn it into blocks
        pass


class TestDelegateFullFlow(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.get_event_loop()
        driver = MetaDataStorage()
        driver.flush()

    def tearDown(self):
        self.ctx.destroy()

    def test_block_number_increments_properly(self):
        mock_master = ComplexMockMasternode(
            ctx=self.ctx,
            delegate_nbn='ipc:///tmp/n1/block_notifications',
            delegate_work='ipc:///tmp/n1/incoming_work',
            wallet=mnw1
        )

        d = Delegate(
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            constitution=constitution,
            wallet=dw1,
            overwrite=True
        )

        # d.nbn_inbox.verify = False
        d.work_inbox.verify = False
        d.running = True

        d.parameters.sockets = {
            mnw1.verifying_key().hex(): 'ipc:///tmp/n2'
        }

        async def run():
            await asyncio.sleep(0.3)
            self.assertEqual(d.driver.latest_block_num, 0)

            await mock_master.send_new_block_to_socket()

            # Assert Block num 1
            await asyncio.sleep(0.3)
            self.assertEqual(d.driver.latest_block_num, 1)

            await mock_master.send_to_work_socket()

            w = await mock_master.mn_agg.recv_multipart()

            b = canonical.get_genesis_block()
            b['blockNum'] = 2

            await mock_master.send_new_block_to_socket(b)

            # Assert Block num 2
            await asyncio.sleep(0.3)
            self.assertEqual(d.driver.latest_block_num, 2)

            d.nbn_inbox.stop()
            d.work_inbox.stop()
            d.stop()

            self.loop.stop()

        tasks = asyncio.gather(
            d.work_inbox.serve(),
            d.nbn_inbox.serve(),
            d.run(),
            run()
        )

        with suppress(RuntimeError):
            self.loop.run_until_complete(tasks)

    def test_acquire_work_if_no_one_connected_returns(self):
        d = Delegate(
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            constitution=constitution,
            wallet=dw1,
            overwrite=True
        )

        self.loop.run_until_complete(d.acquire_work())

    def test_acquire_work_for_one_master_returns_a_single_tx_batch(self):
        mock_master = ComplexMockMasternode(
            ctx=self.ctx,
            delegate_nbn='ipc:///tmp/n1/block_notifications',
            delegate_work='ipc:///tmp/n1/incoming_work',
            wallet=mnw1
        )

        d = Delegate(
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            constitution=constitution,
            wallet=dw1,
            overwrite=True
        )

        d.running = True

        d.parameters.sockets = {
            mnw1.verifying_key().hex(): 'ipc:///tmp/n2'
        }

        args_1 = ('hi', 'hello')
        args_2 = ('howdy', 'yo')
        args_3 = ('yeehaw', 'p')

        mock_master.tx_batcher.queue.extend([
            make_tx(mnw1.verifying_key(), *args_1),
            make_tx(mnw1.verifying_key(), *args_2),
            make_tx(mnw1.verifying_key(), *args_3),
        ])

        async def stop():
            await asyncio.sleep(0.3)
            d.work_inbox.stop()

        tasks = asyncio.gather(
            d.work_inbox.serve(),
            mock_master.send_to_work_socket(),
            d.acquire_work(),
            stop()
        )

        _, _, r, _ = self.loop.run_until_complete(tasks)
        print(r)

    def test_acquire_work_for_two_masters_returns_two_tx_batchs(self):
        mock_master = ComplexMockMasternode(
            ctx=self.ctx,
            delegate_nbn='ipc:///tmp/n1/block_notifications',
            delegate_work='ipc:///tmp/n1/incoming_work',
            wallet=mnw1
        )

        mock_master_2 = ComplexMockMasternode(
            ctx=self.ctx,
            delegate_nbn='ipc:///tmp/n1/block_notifications',
            delegate_work='ipc:///tmp/n1/incoming_work',
            wallet=mnw2,
            ipc='n3'
        )

        d = Delegate(
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            constitution=constitution,
            wallet=dw1,
            overwrite=True
        )

        d.running = True

        d.parameters.sockets = {
            mnw1.verifying_key().hex(): 'ipc:///tmp/n2',
            mnw2.verifying_key().hex(): 'ipc:///tmp/n3'
        }

        mock_master.send_to_work_socket()

        args_1 = ('hi', 'hello')
        args_2 = ('howdy', 'yo')
        args_3 = ('yeehaw', 'p')

        mock_master.tx_batcher.queue.extend([
            make_tx(mnw1.verifying_key(), *args_1),
            make_tx(mnw1.verifying_key(), *args_2),
            make_tx(mnw1.verifying_key(), *args_3),
        ])

        ### TXS for master 2
        args_4 = ('aaa', 'bbb')
        args_5 = ('123', 'xxx')
        args_6 = ('456', 'zzz')

        mock_master_2.tx_batcher.queue.extend([
            make_tx(mnw2.verifying_key(), *args_4),
            make_tx(mnw2.verifying_key(), *args_5),
            make_tx(mnw2.verifying_key(), *args_6),
        ])

        async def stop():
            await asyncio.sleep(0.3)
            d.work_inbox.stop()

        tasks = asyncio.gather(
            d.work_inbox.serve(),
            mock_master.send_to_work_socket(),
            mock_master_2.send_to_work_socket(),
            d.acquire_work(),
            stop()
        )

        _, _, _, r, _ = self.loop.run_until_complete(tasks)
        print(r[0])
        print(r[1])

    def test_acquire_work_returns_empty_self_signed_tx_batches_if_timeout_hit(self):
        mock_master = ComplexMockMasternode(
            ctx=self.ctx,
            delegate_nbn='ipc:///tmp/n1/block_notifications',
            delegate_work='ipc:///tmp/n1/incoming_work',
            wallet=mnw1
        )

        mock_master_2 = ComplexMockMasternode(
            ctx=self.ctx,
            delegate_nbn='ipc:///tmp/n1/block_notifications',
            delegate_work='ipc:///tmp/n1/incoming_work',
            wallet=mnw2,
            ipc='n3'
        )

        d = Delegate(
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            constitution=constitution,
            wallet=dw1,
            overwrite=True
        )

        d.running = True

        d.parameters.sockets = {
            mnw1.verifying_key().hex(): 'ipc:///tmp/n2',
            mnw2.verifying_key().hex(): 'ipc:///tmp/n3',
            Wallet().verifying_key().hex(): 'ipc:///'
        }

        mock_master.send_to_work_socket()

        args_1 = ('hi', 'hello')
        args_2 = ('howdy', 'yo')
        args_3 = ('yeehaw', 'p')

        mock_master.tx_batcher.queue.extend([
            make_tx(mnw1.verifying_key(), *args_1),
            make_tx(mnw1.verifying_key(), *args_2),
            make_tx(mnw1.verifying_key(), *args_3),
        ])

        ### TXS for master 2
        args_4 = ('aaa', 'bbb')
        args_5 = ('123', 'xxx')
        args_6 = ('456', 'zzz')

        mock_master_2.tx_batcher.queue.extend([
            make_tx(mnw2.verifying_key(), *args_4),
            make_tx(mnw2.verifying_key(), *args_5),
            make_tx(mnw2.verifying_key(), *args_6),
        ])

        async def stop():
            await asyncio.sleep(0.3)
            d.work_inbox.stop()

        tasks = asyncio.gather(
            d.work_inbox.serve(),
            mock_master.send_to_work_socket(),
            mock_master_2.send_to_work_socket(),
            d.acquire_work(),
            stop()
        )

        _, _, _, r, _ = self.loop.run_until_complete(tasks)
        print(r[0])
        print(r[1])
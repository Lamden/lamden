from unittest import TestCase
from cilantro_ee.nodes.delegate.delegate import Delegate

from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.core import canonical
from cilantro_ee.storage import MetaDataStorage

import zmq.asyncio
import asyncio

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

n1 = '/tmp/n1'


class ComplexMockMasternode:
    def __init__(self, ctx: zmq.asyncio.Context, delegate_work, delegate_nbn, wallet=Wallet()):
        # Store delegate work socket
        # Store delegate nbn socket
        self.ctx = ctx

        self.delegate_work = self.ctx.socket(zmq.DEALER)
        self.delegate_work.connect(delegate_work)

        self.delegate_nbn = self.ctx.socket(zmq.DEALER)
        self.delegate_nbn.connect(delegate_nbn)

        self.mn_agg = self.ctx.socket(zmq.ROUTER)
        self.mn_agg.bind('ipc:///tmp/n2/block_aggregator')

        self.mn_nbn = self.ctx.socket(zmq.ROUTER)
        self.mn_nbn.bind('ipc:///tmp/n2/block_notifications')

        self.wallet = wallet
        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=[])

    async def send_to_work_socket(self, work=None):
        await self.delegate_work.send(self.tx_batcher.make_empty_batch())

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
        driver = MetaDataStorage()
        driver.flush()

    def tearDown(self):
        self.ctx.destroy()

    def test_init(self):
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
            await asyncio.sleep(0.5)
            await mock_master.send_new_block_to_socket()
            print('sent block 0')

            await mock_master.send_to_work_socket()

            w = await mock_master.mn_agg.recv_multipart()
            print(w)

            b = canonical.get_genesis_block()
            b['blockNum'] = 2

            await mock_master.send_new_block_to_socket(b)
            print('sent block')

        tasks = asyncio.gather(
            d.work_inbox.serve(),
            d.nbn_inbox.serve(),
            d.run(),
            run()
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)


        # send nbn (first block)
        # send work
        # send nbn
from cilantro_ee.nodes.base import Node
from unittest import TestCase

import asyncio
import zmq.asyncio
from cilantro_ee.storage import BlockchainDriver, MasterStorage
from cilantro_ee.nodes.catchup import BlockServer
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.sockets.struct import SocketStruct

async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()

class ShimNBN:
    def __init__(self):
        self.q = []


class ShimNode(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.caught_up_blocks = []

    def process_block(self, block):
        self.caught_up_blocks.append(block)


class TestNode(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.t = BlockchainDriver()
        self.c = MasterStorage()
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()
        self.t.flush()
        self.c.drop_collections()
        self.loop.close()

    def test_catchup(self):
        fake_block_1 = {
            'blockNum': 1,
            'subBlocks': []
        }

        fake_block_2 = {
            'blockNum': 2,
            'subBlocks': []
        }
        self.c.store_block(fake_block_1)
        self.c.store_block(fake_block_2)

        mn_wallets = [Wallet() for _ in range(2)]
        dl_wallets = [Wallet() for _ in range(2)]

        constitution = {
            'masternodes': [mn.verifying_key().hex() for mn in mn_wallets],
            'delegates': [dl.verifying_key().hex() for dl in dl_wallets],
            'masternode_min_quorum': 2,
            'delegate_min_quorum': 2,
        }

        n = Node(socket_base='tcp://127.0.0.1', ctx=self.ctx, constitution=constitution, wallet=mn_wallets[0])

        w = Wallet()
        m = BlockServer(w, 'tcp://127.0.0.1', self.ctx, linger=500, poll_timeout=500)

        tasks = asyncio.gather(
            m.serve(),
            n.catchup(SocketStruct.from_string('tcp://127.0.0.1:10004')),
            stop_server(m, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        print(res)
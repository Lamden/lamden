from cilantro_ee.nodes.masternode.new_mn import NewMasternode
from unittest import TestCase

import zmq.asyncio
import asyncio


class TestNewMasternode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        mn = NewMasternode(ip='127.0.0.1', ctx=self.ctx, signing_key=b'\x00'*32, name='MasterTest')

        self.loop.run_until_complete(mn.start())
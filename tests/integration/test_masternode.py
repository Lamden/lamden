from cilantro_ee.nodes.masternode.new_mn import NewMasternode
from unittest import TestCase
from cilantro_ee.core.sockets.services import _socket
from cilantro_ee.services.overlay.discovery import *
from cilantro_ee.services.overlay.discovery import DiscoveryServer
from cilantro_ee.constants.overlay_network import PEPPER
import zmq
import zmq.asyncio
from cilantro_ee.core.crypto.wallet import Wallet
import zmq.asyncio
import asyncio


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestNewMasternode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        w1 = Wallet()
        w2 = Wallet()

        bootnodes = [_socket('tcp://127.0.0.1:10999'),
                     _socket('tcp://127.0.0.1:13999')]

        d1 = DiscoveryServer(bootnodes[0], w1, pepper=PEPPER.encode(), ctx=self.ctx, linger=1000, poll_timeout=1000)
        d2 = DiscoveryServer(bootnodes[1], w2, pepper=PEPPER.encode(), ctx=self.ctx, linger=1000, poll_timeout=1000)

        const = {
            "masternodes": {
                "vk_list": [
                    w1.verifying_key().hex(),
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    w2.verifying_key().hex(),
                ],
                "min_quorum": 1
            },
            "witnesses": {},
            "schedulers": {},
            "notifiers": {},
            "enable_stamps": False,
            "enable_nonces": False
        }

        mn = NewMasternode(ip='127.0.0.1',
                           ctx=self.ctx,
                           signing_key=b'\x00' * 32,
                           name='MasterTest',
                           constitution=const,
                           bootnodes=bootnodes,
                           overwrite=True)

        tasks = asyncio.gather(
            d1.serve(),
            d2.serve(),
            stop_server(d1, 1),
            stop_server(d2, 1),
            mn.start()
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

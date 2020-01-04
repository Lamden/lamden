from cilantro_ee.nodes.masternode.masternode import NewMasternode
from unittest import TestCase
from cilantro_ee.networking.discovery import *
import zmq
import zmq.asyncio
from cilantro_ee.crypto import Wallet
import zmq.asyncio
import asyncio
from cilantro_ee.networking import Network
from contracting.client import ContractingClient

import os


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


class TestNewMasternode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        ContractingClient().flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_network_start(self):
        # 4 nodes
        # 2 bootnodes
        # 2 mns, 2 delegates

        bootnodes = ['ipc:///tmp/n1', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()
        masternodes = [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()]

        dw1 = Wallet()
        dw2 = Wallet()
        delegates = [dw1.verifying_key().hex(), dw2.verifying_key().hex()]

        constitution = {
            "masternodes": {
                "vk_list": [
                    mnw1.verifying_key().hex(),
                    mnw2.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key().hex(),
                    dw2.verifying_key().hex()
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
        make_ipc(n1)
        mn1 = NewMasternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                            constitution=constitution, webserver_port=8080)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = NewMasternode(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}', bootnodes=bootnodes,
                            constitution=constitution, webserver_port=8081)

        n3 = '/tmp/n3'
        make_ipc(n3)
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}',
                     bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)

        n4 = '/tmp/n4'
        make_ipc(n4)
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}',
                     bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)


        # should test to see all ready signals are recieved
        tasks = asyncio.gather(
            mn1.start(),
            mn2.start(),
            d1.start(),
            d2.start()
        )

        async def run():
            await tasks
            await asyncio.sleep(5)
            mn1.stop()
            mn2.stop()
            d1.stop()
            d2.stop()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())

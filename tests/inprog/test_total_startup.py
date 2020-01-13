from unittest import TestCase
import zmq.asyncio
import asyncio
from contracting.client import ContractingClient
from cilantro_ee.crypto.wallet import Wallet

from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate

import os

def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass

class TestTotalEndToEnd(TestCase):
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
        mn1 = Masternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8080)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = Masternode(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8081)

        n3 = '/tmp/n3'
        make_ipc(n3)
        d1 = Delegate(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}',
                      constitution=constitution, bootnodes=bootnodes)

        n4 = '/tmp/n4'
        make_ipc(n4)
        d2 = Delegate(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}',
                      constitution=constitution, bootnodes=bootnodes)


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
            print('STOP')
            mn1.stop()
            mn2.stop()
            d1.stop()
            d2.stop()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())
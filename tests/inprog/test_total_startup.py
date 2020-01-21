from unittest import TestCase

from tests.inprog.orchestrator import *

import zmq.asyncio
from contracting.client import ContractingClient

class TestTotalEndToEnd(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        ContractingClient().flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_network_start_large(self):
        # 16 nodes
        # 2 bootnodes
        # 8 mns, 8 delegates

        bootnodes = ['ipc:///tmp/n1', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()
        mnw3 = Wallet()
        mnw4 = Wallet()
        mnw5 = Wallet()
        mnw6 = Wallet()
        mnw7 = Wallet()
        mnw8 = Wallet()

        dw9 = Wallet()
        dw10 = Wallet()
        dw11 = Wallet()
        dw12 = Wallet()
        dw13 = Wallet()
        dw14 = Wallet()
        dw15 = Wallet()
        dw16 = Wallet()

        constitution = {
            "masternodes": [
                    mnw1.verifying_key().hex(),
                    mnw2.verifying_key().hex(),
                    mnw3.verifying_key().hex(),
                    mnw4.verifying_key().hex(),
                    mnw5.verifying_key().hex(),
                    mnw6.verifying_key().hex(),
                    mnw7.verifying_key().hex(),
                    mnw8.verifying_key().hex(),
                ],
            "delegates": [
                dw9.verifying_key().hex(),
                dw10.verifying_key().hex(),
                dw11.verifying_key().hex(),
                dw12.verifying_key().hex(),
                dw13.verifying_key().hex(),
                dw14.verifying_key().hex(),
                dw15.verifying_key().hex(),
                dw16.verifying_key().hex(),
            ],
            "masternode_min_quorum": 6,
            "delegate_min_quorum": 8,
            "witnesses": {},
            "schedulers": {},
            "notifiers": {},
            "enable_stamps": False,
            "enable_nonces": False
        }

        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = Masternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8081)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = Masternode(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8082)

        n3 = '/tmp/n3'
        make_ipc(n3)
        mn3 = Masternode(wallet=mnw3, ctx=self.ctx, socket_base=f'ipc://{n3}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8083)

        n4 = '/tmp/n4'
        make_ipc(n4)
        mn4 = Masternode(wallet=mnw4, ctx=self.ctx, socket_base=f'ipc://{n4}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8084)

        n5 = '/tmp/n5'
        make_ipc(n5)
        mn5 = Masternode(wallet=mnw5, ctx=self.ctx, socket_base=f'ipc://{n5}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8085)

        n6 = '/tmp/n6'
        make_ipc(n6)
        mn6 = Masternode(wallet=mnw6, ctx=self.ctx, socket_base=f'ipc://{n6}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8086)

        n7 = '/tmp/n7'
        make_ipc(n7)
        mn7 = Masternode(wallet=mnw7, ctx=self.ctx, socket_base=f'ipc://{n7}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8087)

        n8 = '/tmp/n8'
        make_ipc(n8)
        mn8 = Masternode(wallet=mnw8, ctx=self.ctx, socket_base=f'ipc://{n8}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8088)

        n9 = '/tmp/n9'
        make_ipc(n9)
        d9 = Delegate(wallet=dw9, ctx=self.ctx, socket_base=f'ipc://{n9}', constitution=constitution,
                      bootnodes=bootnodes)

        n10 = '/tmp/n10'
        make_ipc(n10)
        d10 = Delegate(wallet=dw10, ctx=self.ctx, socket_base=f'ipc://{n10}', constitution=constitution,
                       bootnodes=bootnodes)

        n11 = '/tmp/n11'
        make_ipc(n11)
        d11 = Delegate(wallet=dw11, ctx=self.ctx, socket_base=f'ipc://{n11}', constitution=constitution,
                       bootnodes=bootnodes)

        n12 = '/tmp/n12'
        make_ipc(n12)
        d12 = Delegate(wallet=dw12, ctx=self.ctx, socket_base=f'ipc://{n12}', constitution=constitution,
                       bootnodes=bootnodes)

        n13 = '/tmp/n13'
        make_ipc(n13)
        d13 = Delegate(wallet=dw13, ctx=self.ctx, socket_base=f'ipc://{n13}', constitution=constitution,
                       bootnodes=bootnodes)

        n14 = '/tmp/n14'
        make_ipc(n14)
        d14 = Delegate(wallet=dw14, ctx=self.ctx, socket_base=f'ipc://{n14}', constitution=constitution,
                       bootnodes=bootnodes)

        n15 = '/tmp/n15'
        make_ipc(n15)
        d15 = Delegate(wallet=dw15, ctx=self.ctx, socket_base=f'ipc://{n15}', constitution=constitution,
                       bootnodes=bootnodes)

        n16 = '/tmp/n16'
        make_ipc(n16)
        d16 = Delegate(wallet=dw16, ctx=self.ctx, socket_base=f'ipc://{n16}', constitution=constitution,
                       bootnodes=bootnodes)


        # should test to see all ready signals are recieved
        tasks = asyncio.gather(
            mn1.start(),
            mn2.start(),
            mn3.start(),
            mn4.start(),
            mn5.start(),
            mn6.start(),
            mn7.start(),
            mn8.start(),
            d9.start(),
            d10.start(),
            d11.start(),
            d12.start(),
            d13.start(),
            d14.start(),
            d15.start(),
            d16.start(),
        )

        async def run():
            await tasks
            mn1.stop()
            mn2.stop()
            mn3.stop()
            mn4.stop()
            mn5.stop()
            mn6.stop()
            mn7.stop()
            mn8.stop()
            d9.stop()
            d10.stop()
            d11.stop()
            d12.stop()
            d13.stop()
            d14.stop()
            d15.stop()
            d16.stop()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())

    def test_network_bootup(self):
        bootnodes = ['ipc:///tmp/n1', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()

        dw1 = Wallet()
        dw2 = Wallet()

        constitution = {
            'masternodes': [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
            'delegates': [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
            'witnesses': [],
            'schedulers': [],
            'notifiers': [],
            'enable_stamps': False,
            'enable_nonces': False,
            'masternode_min_quorum': 2,
            'delegate_min_quorum': 2,
            'witness_min_quorum': 0,
            'notifier_min_quorum': 0,
            'scheduler_min_quorum': 0
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
            mn1.stop()
            mn2.stop()
            d1.stop()
            d2.stop()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())

    def test_tx_network_bootup(self):
        bootnodes = ['ipc:///tmp/n1', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()

        dw1 = Wallet()
        dw2 = Wallet()

        constitution = {
            'masternodes': [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
            'delegates': [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
            'witnesses': [],
            'schedulers': [],
            'notifiers': [],
            'enable_stamps': False,
            'enable_nonces': False,
            'masternode_min_quorum': 2,
            'delegate_min_quorum': 2,
            'witness_min_quorum': 0,
            'notifier_min_quorum': 0,
            'scheduler_min_quorum': 0
        }

        md1 = IsolatedDriver()
        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = Masternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8080, driver=md1)

        md2 = IsolatedDriver()
        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = Masternode(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8081, driver=md2)

        dd1 = IsolatedDriver()
        n3 = '/tmp/n3'
        make_ipc(n3)
        d1 = Delegate(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}',
                      constitution=constitution, bootnodes=bootnodes, driver=dd1)

        dd2 = IsolatedDriver()
        n4 = '/tmp/n4'
        make_ipc(n4)
        d2 = Delegate(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}',
                      constitution=constitution, bootnodes=bootnodes, driver=dd2)

        # should test to see all ready signals are recieved
        tasks = asyncio.gather(
            mn1.start(),
            mn2.start(),
            d1.start(),
            d2.start()
        )

        async def run():
            await tasks
            async with aiohttp.ClientSession() as session:
                r = await session.post('http://127.0.0.1:8081/', data=make_tx_packed(mnw2.verifying_key(), 'testing', 'test', drivers=[md1, md2, dd1, dd2]))

            res = await r.json()
            print(res)
            #self.assertEqual(res['success'], 'Transaction successfully submitted to the network.')
            await asyncio.sleep(10)
            mn1.stop()
            mn2.stop()
            d1.stop()
            d2.stop()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())

    def test_tx2_network_bootup(self):
        bootnodes = ['ipc:///tmp/n1']

        mnw1 = Wallet()
        mnw2 = Wallet()

        dw1 = Wallet()
        dw2 = Wallet()

        constitution = {
            'masternodes': [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
            'delegates': [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
            'witnesses': [],
            'schedulers': [],
            'notifiers': [],
            'enable_stamps': False,
            'enable_nonces': False,
            'masternode_min_quorum': 2,
            'delegate_min_quorum': 2,
            'witness_min_quorum': 0,
            'notifier_min_quorum': 0,
            'scheduler_min_quorum': 0
        }

        md1 = IsolatedDriver()
        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = Masternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                         constitution=deepcopy(constitution), webserver_port=8080, driver=md1)

        md2 = IsolatedDriver()
        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = Masternode(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}', bootnodes=bootnodes,
                         constitution=deepcopy(constitution), webserver_port=8081, driver=md2)

        dd1 = IsolatedDriver()
        n3 = '/tmp/n3'
        make_ipc(n3)
        d1 = Delegate(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}',
                      constitution=deepcopy(constitution), bootnodes=bootnodes, driver=dd1)

        dd2 = IsolatedDriver()
        n4 = '/tmp/n4'
        make_ipc(n4)
        d2 = Delegate(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}',
                      constitution=deepcopy(constitution), bootnodes=bootnodes, driver=dd2)

        # should test to see all ready signals are recieved
        tasks = asyncio.gather(
            mn1.start(),
            mn2.start(),
            d1.start(),
            d2.start()
        )

        async def run():
            await tasks
            async with aiohttp.ClientSession() as session:
                r = await session.post('http://127.0.0.1:8081/', data=
                make_tx_packed(
                    mnw2.verifying_key(),
                    'testing',
                    'test',
                    sender=Wallet(),
                    kwargs={},
                    drivers=[md1, md2, dd1, dd2]
                )
            )

            res = await r.json()
            print(res)
            #self.assertEqual(res['success'], 'Transaction successfully submitted to the network.')
            await asyncio.sleep(2)
            async with aiohttp.ClientSession() as session:
                r = await session.post('http://127.0.0.1:8081/', data=
                make_tx_packed(
                    mnw2.verifying_key(),
                    'testing',
                    'test',
                    sender=Wallet(),
                    kwargs={},
                    drivers=[md1, md2, dd1, dd2]
                )
            )

            res = await r.json()
            await asyncio.sleep(2)
            async with aiohttp.ClientSession() as session:
                r = await session.post('http://127.0.0.1:8081/', data=
                make_tx_packed(
                    mnw2.verifying_key(),
                    'testing',
                    'test',
                    sender=Wallet(),
                    kwargs={},
                    drivers=[md1, md2, dd1, dd2]
                )
            )

            res = await r.json()
            await asyncio.sleep(2)
            mn1.stop()
            mn2.stop()
            d1.stop()
            d2.stop()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())

    def test_orchestrator(self):
        mns, dls = make_network(2, 2, self.ctx)

        start_up = make_start_awaitable(mns, dls)

        async def test():
            await start_up
            await send_tx(mns[1], mns + dls, contract='testing', function='test', sender=Wallet())
            await send_tx(mns[1], mns + dls, contract='testing', function='test', sender=Wallet())
            await send_tx(mns[1], mns + dls, contract='testing', function='test', sender=Wallet())

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())
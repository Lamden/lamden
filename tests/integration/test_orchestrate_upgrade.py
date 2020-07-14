import unittest
from tests.inprog.orchestrator import *
from cilantro.crypto.wallet import Wallet
import zmq.asyncio
from contracting.client import ContractingClient
from decimal import Decimal
from cilantro import storage
from .mock import mocks
import contracting
import cilantro
import importlib
from cilantro.nodes import base
from cilantro.upgrade import reload_module, build_pepper2, run_install, get_version, version_reboot


class TestUpgradeOrchestration(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.ctx.max_sockets = 50_000
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        ContractingClient().flush()
        storage.BlockStorage().drop_collections()

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_transaction_multiprocessing(self):

        candidate = Wallet()
        candidate2 = Wallet()
        stu = Wallet()
        stu2 = Wallet()

        # o = Orchestrator(2, 4, self.ctx)
        o = Orchestrator(3, 4, self.ctx)

        block_0 = []

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_delegates'
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 99_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 200_000,
                'to': 'elect_delegates'
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 88_000,
                'to': stu2.verifying_key().hex()
            },
            sender=candidate
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 111_000,
                'to': 'elect_delegates'
            },
            sender=candidate2
            , pidx= 1
        ))

        block_1.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 77_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate2
            , pidx=1
        ))

        block_1.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 222_000,
                'to': 'elect_delegates'
            },
            sender=candidate2
            , pidx=1
        ))

        async def test():
            await o.start_network
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[1], block_1)
            await asyncio.sleep(2)
        #

        # a = o.get_var('currency', 'balances', [o.delegates[1].wallet.verifying_key().hex()])
        # c = o.get_var('currency', 'balances', [o.delegates[0].wallet.verifying_key().hex()])
        a = o.get_var('currency', 'balances', [stu.verifying_key().hex()])
        c = o.get_var('currency', 'balances', [stu2.verifying_key().hex()])

        #
        print(f" a,c ={a,c}")
        # print(a,c)

        # asyncio.start_server(server_coro)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())
        asyncio.sleep(12)
        a = o.get_var('currency', 'balances', [stu.verifying_key().hex()])
        c = o.get_var('currency', 'balances', [stu2.verifying_key().hex()])
        print(f" 2) a,c ={a,c}")

    def test_upgrade_falls_back_and_processes_transactions(self):
        current_branch = get_version()
        current_contracting_branch = get_version(os.path.join(os.path.dirname(contracting.__file__), '..'))

        cil_path = os.path.dirname(cilantro.__file__)
        pepper = build_pepper2()

        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)
        network.flush()

        async def test():
            await network.start()

            for node in network.masternodes + network.delegates:
                node.obj.upgrade_manager.testing = True

            await asyncio.sleep(4)

            await network.fund(network.masternodes[0].wallet.verifying_key)
            await network.fund(network.masternodes[1].wallet.verifying_key)
            await network.fund(network.delegates[0].wallet.verifying_key)
            await network.fund(network.delegates[1].wallet.verifying_key)
            await network.fund(network.delegates[2].wallet.verifying_key)

            # This will just run an upgrade that doesn't change anything
            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                kwargs={
                    'cilantro_branch_name': current_branch,
                    'contracting_branch_name': current_contracting_branch,
                    'pepper': pepper,
                },
                wallet=network.masternodes[0].wallet
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                wallet=network.masternodes[1].wallet,
                mn_idx=0
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                wallet=network.delegates[0].wallet,
                mn_idx=0
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                wallet=network.delegates[1].wallet,
                mn_idx=0
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 123,
                    'to': 'test1'
                },
                wallet=network.masternodes[0].wallet,
                mn_idx=1
            )

            await network.make_and_push_tx(
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 321,
                    'to': 'test2'
                },
                wallet=network.masternodes[1].wallet,
                mn_idx=0
            )

            await asyncio.sleep(4)

        # asyncio.start_server(server_coro)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        for node in network.masternodes + network.delegates:
            v = node.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=['test1'])
            v2 = node.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=['test2'])
            self.assertEqual(v, 123)
            self.assertEqual(v2, 321)

            print(f'node={node.wallet.verifying_key} lock={v} test={v2}')
            # self.assertDictEqual(v, {candidate.verifying_key().hex(): 1})
        print('OK')

    def test_upgrade_to_different_branch_hot_reloads_cilantro(self):
        new_branch = 'dev-upgrade-mock-branch'
        current_branch = get_version()
        current_contracting_branch = get_version(os.path.join(os.path.dirname(contracting.__file__), '..'))

        pepper = '7fff3105b123ceaa32dbae4487ecc9fbfc04ff80efd28cfb1f706999ceea2880'

        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)
        network.flush()

        async def test():
            await network.start()

            for node in network.masternodes + network.delegates:
                node.obj.upgrade_manager.testing = True

            await asyncio.sleep(4)

            await network.fund(network.masternodes[0].wallet.verifying_key)
            await network.fund(network.masternodes[1].wallet.verifying_key)
            await network.fund(network.delegates[0].wallet.verifying_key)
            await network.fund(network.delegates[1].wallet.verifying_key)
            await network.fund(network.delegates[2].wallet.verifying_key)

            # This will just run an upgrade that doesn't change anything
            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                kwargs={
                    'cilantro_branch_name': new_branch,
                    'contracting_branch_name': current_contracting_branch,
                    'pepper': pepper,
                },
                wallet=network.masternodes[0].wallet
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                wallet=network.masternodes[1].wallet,
                mn_idx=0
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                wallet=network.delegates[0].wallet,
                mn_idx=0
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                wallet=network.delegates[1].wallet,
                mn_idx=0
            )

            await asyncio.sleep(4)


        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        for node in network.masternodes + network.delegates:
            self.assertTrue(node.obj.upgrade_manager.testing_flag)

    def test_impor(self):
        import importlib
        import os
        import A

        A.a()

        os.rename('A.py', 'A_change.py')
        os.rename('B.py', 'A.py')

        importlib.reload(A)

        A.a()

        os.rename('A.py', 'B.py')
        os.rename('A_change.py', 'A.py')

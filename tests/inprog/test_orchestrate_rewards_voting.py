import unittest
from tests.inprog.orchestrator import *
from cilantro_ee.crypto.wallet import Wallet
import zmq.asyncio
from contracting.client import ContractingClient
from decimal import Decimal
from cilantro_ee.storage import MasterStorage


class TestGovernanceOrchestration(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        ContractingClient().flush()
        MasterStorage().drop_collections()

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_orchestrator(self):
        mns, dls = make_network(2, 4, self.ctx)

        start_up = make_start_awaitable(mns, dls)

        candidate = Wallet()
        stu = Wallet()

        tx1 = make_tx_packed(
            contract_name='currency',
            function_name='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=candidate,
            drivers=[node.driver for node in mns + dls],
            nonce=0,
            stamps=1_000_000,
            processor=mns[1].wallet.verifying_key()
        )

        tx2 = make_tx_packed(
            contract_name='elect_masternodes',
            function_name='register',
            sender=candidate,
            drivers=[node.driver for node in mns + dls],
            nonce=1,
            stamps=1_000_000,
            processor=mns[1].wallet.verifying_key()
        )

        tx3 = make_tx_packed(
            contract_name='currency',
            function_name='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=stu,
            drivers=[node.driver for node in mns + dls],
            nonce=0,
            stamps=1_000_000,
            processor=mns[1].wallet.verifying_key()
        )

        tx4 = make_tx_packed(
            contract_name='elect_masternodes',
            function_name='vote_candidate',
            kwargs={
              'address': candidate.verifying_key().hex()
            },
            sender=stu,
            drivers=[node.driver for node in mns + dls],
            nonce=1,
            stamps=1_000_000,
            processor=mns[1].wallet.verifying_key()
        )

        async def test():
            await start_up
            await asyncio.sleep(3)
            await send_tx_batch(mns[1], [tx1, tx2, tx3, tx4])
            await asyncio.sleep(5)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        for node in mns + dls:
            v = node.driver.get_var(
                contract='elect_masternodes',
                variable='candidate_votes',
                arguments=[])
            self.assertDictEqual(v, {candidate.verifying_key().hex(): 1})

    def test_new_orchestrator(self):
        candidate = Wallet()
        stu = Wallet()

        o = Orchestrator(2, 4, self.ctx)
        txs = []

        txs.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=candidate
        ))

        txs.append(o.make_tx(
            contract='elect_masternodes',
            function='register',
            sender=candidate
        ))

        txs.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=stu
        ))

        txs.append(o.make_tx(
            contract='elect_masternodes',
            function='vote_candidate',
            kwargs={
                'address': candidate.verifying_key().hex()
            },
            sender=stu,
        ))

        async def test():

            await o.start_network
            await asyncio.sleep(1)
            await send_tx_batch(o.masternodes[0], txs)
            await asyncio.sleep(3)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        v = o.get_var('elect_masternodes', 'top_candidate')
        self.assertEqual(v, candidate.verifying_key().hex())

        v = o.get_var('currency', 'balances', ['blackhole'])
        self.assertEqual(v, 1)

    def test_new_orchestrator_2nd_mn_submission(self):
        candidate = Wallet()
        stu = Wallet()

        o = Orchestrator(2, 4, self.ctx)
        txs = []

        txs.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=candidate,
            pidx=1
        ))

        txs.append(o.make_tx(
            contract='elect_masternodes',
            function='register',
            sender=candidate,
            pidx=1
        ))

        txs.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=stu,
            pidx=1
        ))

        txs.append(o.make_tx(
            contract='elect_masternodes',
            function='vote_candidate',
            kwargs={
                'address': candidate.verifying_key().hex()
            },
            sender=stu,
            pidx=1
        ))

        async def test():

            await o.start_network
            await asyncio.sleep(3)
            await send_tx_batch(o.masternodes[1], txs)
            await asyncio.sleep(5)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        v = o.get_var('elect_masternodes', 'candidate_votes')
        self.assertDictEqual(v, {candidate.verifying_key().hex(): 1})

        v = o.get_var('currency', 'balances', ['blackhole'])
        self.assertEqual(v, 0.2)

    def test_introduce_and_pass_motion_masternodes(self):
        stu = Wallet()
        candidate = Wallet()

        o = Orchestrator(2, 4, self.ctx)

        block_0 = []

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='elect_masternodes',
            function='register',
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=stu
        ))

        block_0.append(o.make_tx(
            contract='elect_masternodes',
            function='vote_candidate',
            kwargs={
                'address': candidate.verifying_key().hex()
            },
            sender=stu,
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'masternodes',
                'value': ('introduce_motion', 2)
            },
            sender=o.masternodes[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'masternodes',
                'value': ('vote_on_motion', True)
            },
            sender=o.masternodes[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'masternodes',
                'value': ('vote_on_motion', True)
            },
            sender=o.masternodes[1].wallet
        ))

        async def test():

            await o.start_network
            await asyncio.sleep(5)
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(2)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        v = o.get_var('masternodes', 'S', ['members'])
        self.assertListEqual(v, [
            o.masternodes[0].wallet.verifying_key().hex(),
            o.masternodes[1].wallet.verifying_key().hex(),
            candidate.verifying_key().hex()
        ])

    def test_introduce_and_pass_motion_masternodes_affects_parameters(self):
        stu = Wallet()
        candidate = Wallet()

        o = Orchestrator(2, 4, self.ctx)

        block_0 = []

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='elect_masternodes',
            function='register',
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_masternodes'
            },
            sender=stu
        ))

        block_0.append(o.make_tx(
            contract='elect_masternodes',
            function='vote_candidate',
            kwargs={
                'address': candidate.verifying_key().hex()
            },
            sender=stu,
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'masternodes',
                'value': ('introduce_motion', 2)
            },
            sender=o.masternodes[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'masternodes',
                'value': ('vote_on_motion', True)
            },
            sender=o.masternodes[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'masternodes',
                'value': ('vote_on_motion', True)
            },
            sender=o.masternodes[1].wallet
        ))

        async def test():

            await o.start_network
            await asyncio.sleep(4)
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(7)
            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(7)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        self.assertListEqual(o.masternodes[0].contacts.masternodes, [
            o.masternodes[0].wallet.verifying_key().hex(),
            o.masternodes[1].wallet.verifying_key().hex(),
            candidate.verifying_key().hex()
        ])

        self.assertListEqual(o.masternodes[1].contacts.masternodes, [
            o.masternodes[0].wallet.verifying_key().hex(),
            o.masternodes[1].wallet.verifying_key().hex(),
            candidate.verifying_key().hex()
        ])

    def test_introduce_and_pass_motion_delegates(self):
        stu = Wallet()
        candidate = Wallet()

        o = Orchestrator(2, 4, self.ctx)

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
            contract='elect_delegates',
            function='register',
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_delegates'
            },
            sender=stu
        ))

        block_0.append(o.make_tx(
            contract='elect_delegates',
            function='vote_candidate',
            kwargs={
                'address': candidate.verifying_key().hex()
            },
            sender=stu,
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('introduce_motion', 2)
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[1].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[2].wallet
        ))

        async def test():

            await o.start_network
            await asyncio.sleep(3)
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(3)
            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(3)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        v = o.get_var('delegates', 'S', ['members'])
        self.assertListEqual(v, [
            o.delegates[0].wallet.verifying_key().hex(),
            o.delegates[1].wallet.verifying_key().hex(),
            o.delegates[2].wallet.verifying_key().hex(),
            o.delegates[3].wallet.verifying_key().hex(),
            candidate.verifying_key().hex()
        ])

    def test_introduce_and_pass_motion_delegates_affects_parameters(self):
        stu = Wallet()
        candidate = Wallet()

        o = Orchestrator(2, 4, self.ctx)

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
            contract='elect_delegates',
            function='register',
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_delegates'
            },
            sender=stu
        ))

        block_0.append(o.make_tx(
            contract='elect_delegates',
            function='vote_candidate',
            kwargs={
                'address': candidate.verifying_key().hex()
            },
            sender=stu,
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('introduce_motion', 2)
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[1].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[2].wallet
        ))

        async def test():

            await o.start_network
            await asyncio.sleep(1)
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(2)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        self.assertListEqual(o.delegates[0].contacts.delegates, [
            o.delegates[0].wallet.verifying_key().hex(),
            o.delegates[1].wallet.verifying_key().hex(),
            o.delegates[2].wallet.verifying_key().hex(),
            o.delegates[3].wallet.verifying_key().hex(),
            candidate.verifying_key().hex()
        ])

        self.assertListEqual(o.delegates[1].contacts.delegates, [
            o.delegates[0].wallet.verifying_key().hex(),
            o.delegates[1].wallet.verifying_key().hex(),
            o.delegates[2].wallet.verifying_key().hex(),
            o.delegates[3].wallet.verifying_key().hex(),
            candidate.verifying_key().hex()
        ])

    def test_introduce_and_pass_motion_delegates_then_removes(self):
        stu = Wallet()
        candidate = Wallet()

        o = Orchestrator(2, 4, self.ctx)

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
            contract='elect_delegates',
            function='register',
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_delegates'
            },
            sender=stu
        ))

        block_0.append(o.make_tx(
            contract='elect_delegates',
            function='vote_candidate',
            kwargs={
                'address': candidate.verifying_key().hex()
            },
            sender=stu,
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('introduce_motion', 2)
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[1].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[2].wallet
        ))

        block_2 = []

        block_2.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('introduce_motion', 1, candidate.verifying_key().hex())
            },
            sender=o.delegates[0].wallet
        ))

        block_2.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[0].wallet
        ))

        block_2.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[1].wallet
        ))

        block_2.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.delegates[2].wallet
        ))

        async def test():

            await o.start_network
            await asyncio.sleep(3)
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(3)
            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(3)
            await send_tx_batch(o.masternodes[0], block_2)
            await asyncio.sleep(3)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        v = o.get_var('delegates', 'S', ['members'])
        self.assertListEqual(v, [
            o.delegates[0].wallet.verifying_key().hex(),
            o.delegates[1].wallet.verifying_key().hex(),
            o.delegates[2].wallet.verifying_key().hex(),
            o.delegates[3].wallet.verifying_key().hex(),
        ])

    def test_change_rewards_changes_distribution(self):
        o = Orchestrator(2, 4, self.ctx)

        stu = Wallet()
        candidate = Wallet()

        # Send some crap to get the stamp amount
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
                'amount': 100_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': candidate.verifying_key().hex()
            },
            sender=stu
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'rewards',
                'value': [70, 30, 0, 0]
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'rewards',
                'value': [70, 30, 0, 0]
            },
            sender=o.delegates[1].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'rewards',
                'value': [60, 40, 0, 0]
            },
            sender=o.delegates[2].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'rewards',
                'value': [50, 50, 0, 0]
            },
            sender=o.delegates[3].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'rewards',
                'value': [50, 50, 0, 0]
            },
            sender=o.masternodes[0].wallet
        ))

        block_2 = []

        block_2.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_delegates'
            },
            sender=candidate
        ))

        block_2.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 100_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate
        ))

        block_2.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': candidate.verifying_key().hex()
            },
            sender=stu
        ))


        async def test():
            await o.start_network
            await asyncio.sleep(3)
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(3)

            a = o.get_var('currency', 'balances', [o.masternodes[0].wallet.verifying_key().hex()])
            b = o.get_var('currency', 'balances', [o.delegates[0].wallet.verifying_key().hex()])
            c = o.get_var('currency', 'balances', [o.delegates[1].wallet.verifying_key().hex()])
            d = o.get_var('currency', 'balances', [o.delegates[2].wallet.verifying_key().hex()])
            e = o.get_var('currency', 'balances', [o.delegates[3].wallet.verifying_key().hex()])

            self.assertEqual(a, b)
            self.assertEqual(b, c)
            self.assertEqual(c, d)
            self.assertEqual(d, e)

            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(3)

            await send_tx_batch(o.masternodes[0], block_2)
            await asyncio.sleep(3)

            a = o.get_var('currency', 'balances', [o.masternodes[0].wallet.verifying_key().hex()])
            b = o.get_var('currency', 'balances', [o.delegates[0].wallet.verifying_key().hex()])
            c = o.get_var('currency', 'balances', [o.delegates[1].wallet.verifying_key().hex()])
            d = o.get_var('currency', 'balances', [o.delegates[2].wallet.verifying_key().hex()])
            e = o.get_var('currency', 'balances', [o.delegates[3].wallet.verifying_key().hex()])

            self.assertGreater(a, b)
            self.assertGreater(a, c)
            self.assertGreater(a, d)
            self.assertGreater(a, e)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())


    def test_change_stamps_increases_reward_amounts(self):
        o = Orchestrator(2, 4, self.ctx)

        stu = Wallet()
        candidate = Wallet()

        # Send some crap to get the stamp amount
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
                'amount': 100_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': candidate.verifying_key().hex()
            },
            sender=stu
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'stamp_cost',
                'value': 10_000
            },
            sender=o.delegates[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'stamp_cost',
                'value': 10_000
            },
            sender=o.delegates[1].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'stamp_cost',
                'value': 10_000
            },
            sender=o.delegates[2].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'stamp_cost',
                'value': 10_000
            },
            sender=o.delegates[3].wallet
        ))

        # NEW STAMP COST = 68_000

        block_2 = []

        block_2.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_delegates'
            },
            sender=candidate
        ))

        block_2.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 100_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate
        ))

        block_2.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': candidate.verifying_key().hex()
            },
            sender=stu
        ))

        async def test():
            await o.start_network
            await asyncio.sleep(3)
            d1 = o.get_var('currency', 'balances', [o.masternodes[0].wallet.verifying_key().hex()]) or 0

            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(3)

            d2 = o.get_var('currency', 'balances', [o.masternodes[0].wallet.verifying_key().hex()])

            delta = d2 - d1

            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(3)

            d3 = o.get_var('currency', 'balances', [o.masternodes[0].wallet.verifying_key().hex()])

            await send_tx_batch(o.masternodes[0], block_2)
            await asyncio.sleep(3)

            d4 = o.get_var('currency', 'balances', [o.masternodes[0].wallet.verifying_key().hex()])

            delta_2 = d4 - d3

            self.assertAlmostEqual(delta_2, delta * Decimal(1.67), places=3)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

    def test_one_by_one_network(self):
        o = Orchestrator(1, 1, ctx=self.ctx, min_del_quorum=1, min_mn_quorum=1)

        candidate = Wallet()

        # Send some crap to get the stamp amount
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

        async def test():
            await o.start_network
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(2)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())
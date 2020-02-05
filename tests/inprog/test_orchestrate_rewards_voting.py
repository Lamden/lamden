import unittest
from tests.inprog.orchestrator import *
from cilantro_ee.crypto.wallet import Wallet
import zmq.asyncio
from contracting.client import ContractingClient

from contracting.db.driver import InMemDriver
from cilantro_ee.storage.contract import BlockchainDriver


class TestGovernanceOrchestration(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        ContractingClient().flush()
        asyncio.set_event_loop(self.loop)

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
            await asyncio.sleep(1)
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
            await asyncio.sleep(1)
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[0], block_1)
            await asyncio.sleep(2)

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
                'amount': 10_000,
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
                'amount': 10_000,
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
            sender=o.masternodes[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.masternodes[0].wallet
        ))

        block_1.append(o.make_tx(
            contract='election_house',
            function='vote',
            kwargs={
                'policy': 'delegates',
                'value': ('vote_on_motion', True)
            },
            sender=o.masternodes[1].wallet
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

        self.assertListEqual(o.delegates[0].contacts.masternodes, [
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
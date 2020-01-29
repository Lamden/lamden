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
        mns, dls = make_network(2, 2, self.ctx)

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
            contract_name='elect_masternodes',
            function_name='vote_candidate',
            kwargs={
              'address': candidate.verifying_key().hex()
            },
            sender=stu,
            drivers=[node.driver for node in mns + dls],
            nonce=0,
            stamps=1_000_000,
            processor=mns[1].wallet.verifying_key()
        )

        async def test():
            await start_up
            await asyncio.sleep(1)
            await send_tx_batch(mns[1], [tx1, tx2, tx3])
            await asyncio.sleep(3)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        for node in mns + dls:
            v = node.driver.get_var(
                contract='elect_masters',
                variable='candidate_votes',
                arguments=[])

            print(v)



# def test_vote_for_someone_registered_deducts_tau_and_adds_vote(self):
#     # Give joe money
#     self.currency.transfer(signer='stu', amount=100_000, to='joe')
#
#     # Joe Allows Spending
#     self.currency.approve(signer='joe', amount=100_000, to='master_candidates')
#
#     self.master_candidates.register(signer='joe')
#
#     self.currency.approve(signer='stu', amount=10_000, to='master_candidates')
#
#     env = {'now': Datetime._from_datetime(dt.today())}
#
#     stu_bal = self.currency.balances['stu']
#
#     self.master_candidates.vote_candidate(signer='stu', address='joe', environment=env)
#
#     print(self.master_candidates.executor.driver.pending_writes)
#
#     self.assertEqual(self.currency.balances['stu'], stu_bal - 1)
#     self.assertEqual(self.master_candidates.candidate_votes.get()['joe'], 1)
#     self.assertEqual(self.currency.balances['blackhole'], 1)
#     self.assertEqual(self.master_candidates.candidate_state['last_voted', 'stu'], env['now'])
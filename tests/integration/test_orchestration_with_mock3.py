from cilantro.crypto import transaction
from cilantro.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, InMemDriver
from contracting.client import ContractingClient
import zmq.asyncio
import asyncio
from copy import deepcopy
from unittest import TestCase
import httpx

from tests.integration.mock import mocks


class TestFullFlowWithMocks(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        self.driver = ContractDriver(driver=InMemDriver())
        self.client = ContractingClient(driver=self.driver)
        self.client.flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.client.flush()
        self.driver.flush()
        self.ctx.destroy()
        self.loop.close()

    def test_vote_new_delegate(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        candidate = Wallet()

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': stu.verifying_key
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': candidate.verifying_key
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_delegates'
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='elect_delegates',
                function='register'
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_delegates'
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=stu,
                contract='elect_delegates',
                function='vote_candidate',
                kwargs={
                    'address': candidate.verifying_key
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=network.delegates[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'delegates',
                    'value': ('introduce_motion', 2)
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=network.delegates[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'delegates',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=network.delegates[1].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'delegates',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(4)

            candidate_delegate = mocks.MockDelegate(
                ctx=self.ctx,
                index=999
            )

            candidate_delegate.wallet = candidate

            constitution = deepcopy(network.constitution)
            bootnodes = deepcopy(network.bootnodes)

            constitution['delegates'].append(candidate.verifying_key)

            candidate_delegate.set_start_variables(bootnodes=bootnodes, constitution=constitution)

            await candidate_delegate.start()

            network.delegates.append(candidate_delegate)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'jeff'
                }
            )

            await asyncio.sleep(14)

            self.assertEqual(candidate_delegate.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=['jeff']
            ), 1)

        self.loop.run_until_complete(test())
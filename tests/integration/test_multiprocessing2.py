from lamden.crypto import transaction
from lamden.crypto.wallet import Wallet
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

    def test_process_two_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        stu2 = Wallet()
        candidate = Wallet()
        candidate2 = Wallet()

        N_tx= 3
        w_stu =[]
        for k in range(N_tx):
            w_stu.append(Wallet())

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': w_stu[0].verifying_key
                }
            )
            # for k in range(1,N_tx):
            #     await network.make_and_push_tx(
            #         wallet=mocks.TEST_FOUNDATION_WALLET,
            #         contract='currency',
            #         function='transfer',
            #         kwargs={
            #             'amount': 2,
            #             'to': w_stu[0].verifying_key
            #         }
            #     )


            for k1 in range(N_tx -1):
                # await asyncio.sleep(1)
                k = N_tx - k1 - 2
                await network.make_and_push_tx(
                    wallet=w_stu[k],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 10,
                        'to': w_stu[k+1].verifying_key
                    },
                )
            await asyncio.sleep(2)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[w_stu[N_tx-1].verifying_key]
            ), 10)

        self.loop.run_until_complete(test())


    def test_process_single_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        stu2 = Wallet()
        candidate = Wallet()
        candidate2 = Wallet()

        async def test():
            await network.start()
            network.refresh()

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': stu.verifying_key
                }
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': candidate.verifying_key
                },
            )
            await asyncio.sleep(14)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[candidate.verifying_key]
            ), 1338)

        self.loop.run_until_complete(test())

    def test_delegate_join_and_participate_in_consensus(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        candidate = Wallet()
        candidate2= Wallet()

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
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.delegates[0].wallet.verifying_key
                }
            )
            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.delegates[1].wallet.verifying_key
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

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=stu,
                contract='elect_delegates',
                function='vote_candidate',
                kwargs={
                    'address': candidate.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.delegates[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'delegates',
                    'value': ('introduce_motion', 2)
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.delegates[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'delegates',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(2)

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

            # network.delegates[0].stop()
            network.delegates[1].stop()

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': candidate.verifying_key
                }
            )
            await asyncio.sleep(3)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': candidate2.verifying_key
                },
            )
            await asyncio.sleep(3)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[candidate2.verifying_key]
            ), 1338)

            await asyncio.sleep(3)

        self.loop.run_until_complete(test())

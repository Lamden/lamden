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

    def test_mock_network_init_makes_correct_number_of_nodes(self):
        n = mocks.MockNetwork(num_of_delegates=1, num_of_masternodes=1, ctx=self.ctx)
        self.assertEqual(len(n.masternodes), 1)
        self.assertEqual(len(n.delegates), 1)

    def test_mock_network_init_makes_correct_number_of_nodes_many_nodes(self):
        n = mocks.MockNetwork(num_of_delegates=123, num_of_masternodes=143, ctx=self.ctx)
        self.assertEqual(len(n.masternodes), 143)
        self.assertEqual(len(n.delegates), 123)

    def test_mock_network_init_creates_correct_bootnodes(self):
        # 2 mn, 3 delegate
        expected_ips = [
            'tcp://127.0.0.1:18000',
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002',
            'tcp://127.0.0.1:18003',
            'tcp://127.0.0.1:18004',
        ]

        n = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)

        self.assertEqual(n.masternodes[0].ip, expected_ips[0])
        self.assertEqual(n.masternodes[1].ip, expected_ips[1])
        self.assertEqual(n.delegates[0].ip, expected_ips[2])
        self.assertEqual(n.delegates[1].ip, expected_ips[3])
        self.assertEqual(n.delegates[2].ip, expected_ips[4])

    def test_startup_with_manual_node_creation_and_single_block_works(self):
        m = mocks.MockMaster(ctx=self.ctx, index=1)
        d = mocks.MockDelegate(ctx=self.ctx, index=2)

        bootnodes = {
            m.wallet.verifying_key: m.ip,
            d.wallet.verifying_key: d.ip
        }

        constitution = {
            'masternodes': [m.wallet.verifying_key],
            'delegates': [d.wallet.verifying_key]
        }

        m.set_start_variables(bootnodes, constitution)
        d.set_start_variables(bootnodes, constitution)

        sender = Wallet()

        async def test():
            await asyncio.gather(
                m.start(),
                d.start()
            )

            tx_1 = transaction.build_transaction(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': sender.verifying_key
                },
                stamps=10000,
                nonce=0,
                processor=m.wallet.verifying_key
            )

            tx_2 = transaction.build_transaction(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': 'jeff'
                },
                stamps=5000,
                nonce=0,
                processor=m.wallet.verifying_key
            )

            async with httpx.AsyncClient() as client:
                await client.post('http://0.0.0.0:18081/', data=tx_1)
                await asyncio.sleep(2)
                await client.post('http://0.0.0.0:18081/', data=tx_2)
                await asyncio.sleep(2)

            await asyncio.sleep(2)

            m.stop()
            d.stop()

        self.loop.run_until_complete(test())

        # dbal = dld.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal = m.driver.get_var(contract='currency', variable='balances', arguments=['jeff'])

        # self.assertEqual(dbal, 1338)
        self.assertEqual(mbal, 1338)

    def test_startup_and_blocks_from_network_object_works(self):
        network = mocks.MockNetwork(ctx=self.ctx, num_of_masternodes=1, num_of_delegates=1)

        sender = Wallet()

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': sender.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': 'jeff'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 444,
                    'to': 'stu'
                }
            )

            await asyncio.sleep(2)

            network.stop()

        self.loop.run_until_complete(test())

        v1 = network.get_var(contract='currency', variable='balances', arguments=['jeff'], delegates=True)

        self.assertEqual(v1, 1338)

        v2 = network.get_var(contract='currency', variable='balances', arguments=['stu'])

        self.assertEqual(v2, 444)

    def test_startup_and_blocks_from_network_object_works_no_wait(self):
        network = mocks.MockNetwork(ctx=self.ctx, num_of_masternodes=1, num_of_delegates=1)

        sender = Wallet()

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': sender.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': 'jeff'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=sender,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 444,
                    'to': 'stu'
                }
            )

            await asyncio.sleep(2)

            network.stop()

        self.loop.run_until_complete(test())

        v1 = network.get_var(contract='currency', variable='balances', arguments=['jeff'], delegates=True)

        self.assertEqual(v1, 1338)

        v2 = network.get_var(contract='currency', variable='balances', arguments=['stu'])

        self.assertEqual(v2, 444)
        network.flush()

    def test_add_new_masternode_with_transactions(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)

        stu = Wallet()
        candidate = Wallet()

        print(candidate.verifying_key)

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

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': candidate.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[0].wallet.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[1].wallet.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_100,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='elect_masternodes',
                function='register',
                kwargs={}
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=stu,
                contract='elect_masternodes',
                function='vote_candidate',
                kwargs={
                    'address': candidate.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('introduce_motion', 2)
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[1].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(4)

        self.loop.run_until_complete(test())

        network.stop()

        masters = network.get_var(contract='masternodes', variable='S', arguments=['members'])
        self.assertListEqual(
            masters,
            [*[node.wallet.verifying_key for node in network.masternodes], candidate.verifying_key]
        )

        network.flush()

    def test_vote_new_masternode_in_can_join_quorum_afterwards(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)

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
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[0].wallet.verifying_key
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[1].wallet.verifying_key
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='elect_masternodes',
                function='register'
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=stu,
                contract='elect_masternodes',
                function='vote_candidate',
                kwargs={
                    'address': candidate.verifying_key
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('introduce_motion', 2)
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=network.masternodes[1].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(4)

            candidate_master = mocks.MockMaster(
                ctx=self.ctx,
                index=999
            )

            candidate_master.wallet = candidate

            constitution = deepcopy(network.constitution)
            bootnodes = deepcopy(network.bootnodes)

            constitution['masternodes'].append(candidate.verifying_key)

            candidate_master.set_start_variables(bootnodes=bootnodes, constitution=constitution)

            await candidate_master.start()

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'jeff'
                }
            )

            await asyncio.sleep(6)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'jeff2'
                }
            )

            await asyncio.sleep(6)

            self.assertEqual(candidate_master.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=['jeff']
            ), 1)

            self.assertEqual(candidate_master.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=['jeff2']
            ), 1)

        self.loop.run_until_complete(test())

    def test_vote_new_masternode_in_can_join_and_catches_up_to_state(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)

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

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': candidate.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[0].wallet.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[1].wallet.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_100,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='elect_masternodes',
                function='register'
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_100,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=stu,
                contract='elect_masternodes',
                function='vote_candidate',
                kwargs={
                    'address': candidate.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('introduce_motion', 2)
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[1].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(4)

            candidate_master = mocks.MockMaster(
                ctx=self.ctx,
                index=999
            )

            candidate_master.wallet = candidate

            constitution = deepcopy(network.constitution)
            bootnodes = deepcopy(network.bootnodes)

            constitution['masternodes'].append(candidate.verifying_key)

            candidate_master.set_start_variables(bootnodes=bootnodes, constitution=constitution)

            await candidate_master.start()

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': stu.verifying_key
                }
            )

            await asyncio.sleep(1)

            network.masternodes.append(candidate_master)

            a = network.get_vars(
                contract='currency',
                variable='balances',
                arguments=[stu.verifying_key]
            )

            print(a)

        self.loop.run_until_complete(test())

    def test_vote_new_masternode_in_can_join_and_accept_transactions(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)

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

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': candidate.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[0].wallet.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': network.masternodes[1].wallet.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=candidate,
                contract='elect_masternodes',
                function='register'
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_masternodes'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=stu,
                contract='elect_masternodes',
                function='vote_candidate',
                kwargs={
                    'address': candidate.verifying_key
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('introduce_motion', 2)
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[0].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=network.masternodes[1].wallet,
                contract='election_house',
                function='vote',
                kwargs={
                    'policy': 'masternodes',
                    'value': ('vote_on_motion', True)
                }
            )

            await asyncio.sleep(4)

            candidate_master = mocks.MockMaster(
                ctx=self.ctx,
                index=999
            )

            candidate_master.wallet = candidate

            constitution = deepcopy(network.constitution)
            bootnodes = deepcopy(network.bootnodes)

            constitution['masternodes'].append(candidate.verifying_key)

            candidate_master.set_start_variables(bootnodes=bootnodes, constitution=constitution)

            await candidate_master.start()

            await asyncio.sleep(4)

            network.masternodes.append(candidate_master)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'jeff'
                }
            )

            await asyncio.sleep(4)

            self.assertEqual(candidate_master.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=['jeff']
            ), 1)

        self.loop.run_until_complete(test())

    def test_single_masternode_goes_offline_and_back_on_has_no_problem_rejoining(self):
        network = mocks.MockNetwork(num_of_masternodes=1, num_of_delegates=2, ctx=self.ctx)

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu2'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu3'
                }
            )

            await asyncio.sleep(2)

            m = network.masternodes[0]
            m.stop()

            await asyncio.sleep(2)

            await m.start()

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu3'
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'jeff'
                }
            )

            await asyncio.sleep(2)

            stu = m.driver.get_var(contract='currency', variable='balances', arguments=['stu'])
            stu2 = m.driver.get_var(contract='currency', variable='balances', arguments=['stu2'])
            stu3 = m.driver.get_var(contract='currency', variable='balances', arguments=['stu3'])
            jeff = m.driver.get_var(contract='currency', variable='balances', arguments=['jeff'])

            self.assertEqual(stu, 1)
            self.assertEqual(stu2, 1)
            self.assertEqual(stu3, 2)
            self.assertEqual(jeff, 1)

        self.loop.run_until_complete(test())

    def test_two_masters_one_offline_can_come_back_without_issue(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu'
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu2'
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu3'
                }
            )

            await asyncio.sleep(1)

            m = network.masternodes[0]
            m.stop()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu3'
                },
                mn_idx=1
            )

            await asyncio.sleep(1)

            await m.start()

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'stu3'
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'jeff'
                }
            )

            await asyncio.sleep(1)

            stu = m.driver.get_var(contract='currency', variable='balances', arguments=['stu'])
            stu2 = m.driver.get_var(contract='currency', variable='balances', arguments=['stu2'])
            stu3 = m.driver.get_var(contract='currency', variable='balances', arguments=['stu3'])
            jeff = m.driver.get_var(contract='currency', variable='balances', arguments=['jeff'])

            self.assertEqual(stu, 1)
            self.assertEqual(stu2, 1)
            self.assertEqual(stu3, 3)
            self.assertEqual(jeff, 1)

        self.loop.run_until_complete(test())

    def test_eat_stamps(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=3, ctx=self.ctx)

        code = '''\
@export
def eat_stamps():
    while True:
        pass
'''

        stu = Wallet()
        candidate = Wallet()

        print(candidate.verifying_key)

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='submission',
                function='submit_contract',
                kwargs={
                    'name': 'con_stamp_eater',
                    'code': code
                }
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='con_stamp_eater',
                function='eat_stamps',
                kwargs={},
                stamps=10000
            )

            await asyncio.sleep(4)

        self.loop.run_until_complete(test())

        network.stop()
        network.flush()

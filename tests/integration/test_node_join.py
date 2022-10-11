from lamden.crypto.wallet import Wallet
from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.unit.helpers.mock_transactions import get_introduce_motion_tx, get_vote_tx, get_register_tx, get_approve_tx, get_vote_candidate_tx
from unittest import TestCase
import asyncio
import json
import random

class TestNodeVoteAndJoin(TestCase):
    def setUp(self):
        self.network = LocalNodeNetwork(
            num_of_masternodes=5
        )

        loop = asyncio.get_event_loop()
        while not self.network.all_nodes_started:
            loop.run_until_complete(asyncio.sleep(1))

        self.num_yays_needed = len(self.network.all_nodes) // 2 + 1
        self.num_blocks_total = 1

    def tearDown(self):
        task = asyncio.ensure_future(self.network.stop_all_nodes())
        loop = asyncio.get_event_loop()
        while not task.done():
            loop.run_until_complete(asyncio.sleep(0.1))

    def await_async_process(self, process, *args, **kwargs):
        tasks = asyncio.gather(
            process(*args, **kwargs)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def fund_member(self, wallet):
        for node in self.network.all_nodes:
            node.set_smart_contract_value(
                key=f'currency.balances:{wallet.verifying_key}',
                value=1000000
            )

    def test_single_candidate_winner_can_join_the_network(self):
        new_members_wallet = Wallet()
        self.fund_member(new_members_wallet)

        random_master = random.choice(self.network.masternodes)

        approve_tx = get_approve_tx(wallet=new_members_wallet, processor_vk=random_master.vk, to='elect_masternodes')
        random_master.send_tx(approve_tx)
        self.num_blocks_total += 1

        register_tx = get_register_tx(wallet=new_members_wallet, processor_vk=random_master.vk, nonce=1)
        random_master.send_tx(register_tx)
        self.num_blocks_total += 1

        introduce_motion_tx = get_introduce_motion_tx(policy='masternodes', motion=2, wallet=random_master.wallet, nonce=2)
        random_master.send_tx(json.dumps(introduce_motion_tx).encode())
        self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        for i in range(self.num_yays_needed):
            self.network.masternodes[i].send_tx(
                json.dumps(get_vote_tx(policy='masternodes', vote=True,
                                       wallet=self.network.masternodes[i].wallet,
                                       nonce=3)
                ).encode()
            )

        self.num_blocks_total += self.num_yays_needed

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.network.add_masternode(wallet=new_members_wallet)

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.network.send_tx_to_masternode(random_master.vk)
        self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.assertTrue(self.network.get_masternode(new_members_wallet.verifying_key).node_started)

    def test_multiple_candidates_winner_can_join_the_network(self):
        new_members_wallet = Wallet(); candidate_wallet = Wallet()
        self.fund_member(new_members_wallet); self.fund_member(candidate_wallet)

        random_master = random.choice(self.network.masternodes)

        for w in [candidate_wallet, new_members_wallet]:
            random_master.send_tx(
                get_approve_tx(wallet=w, processor_vk=random_master.vk,
                               to='elect_masternodes')
            )
            self.num_blocks_total += 1

            self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

            random_master.send_tx(
                get_register_tx(wallet=w, processor_vk=random_master.vk, nonce=1)
            )
            self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        voters = [Wallet(), Wallet()]
        for voter in voters:
            self.fund_member(voter)
            random_master.send_tx(
                get_approve_tx(wallet=voter, processor_vk=random_master.vk,
                               to='elect_masternodes', amount=10)
            )
            self.num_blocks_total += 1
            self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

            random_master.send_tx(
                get_vote_candidate_tx(wallet=voter, processor_vk=random_master.vk,
                                      candidate=new_members_wallet.verifying_key,
                                      nonce=1)
            )
            self.num_blocks_total += 1
            self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        random_master.send_tx(
            json.dumps(get_introduce_motion_tx(policy='masternodes', motion=2,
                       wallet=random_master.wallet, nonce=2)).encode()
        )
        self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        for i in range(self.num_yays_needed):
            self.network.masternodes[i].send_tx(
                json.dumps(get_vote_tx(policy='masternodes', vote=True,
                                       wallet=self.network.masternodes[i].wallet,
                                       nonce=3)
                ).encode()
            )
        self.num_blocks_total += self.num_yays_needed

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        for node in self.network.all_nodes:
            self.assertIn(new_members_wallet.verifying_key, node.get_smart_contract_value('masternodes.S:members'))
            self.assertNotIn(candidate_wallet.verifying_key, node.get_smart_contract_value('masternodes.S:members'))

        self.network.add_masternode(wallet=new_members_wallet)

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.network.send_tx_to_masternode(random_master.vk)
        self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.assertTrue(self.network.get_masternode(new_members_wallet.verifying_key).node_started)

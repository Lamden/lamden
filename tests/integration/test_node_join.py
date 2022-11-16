from lamden.crypto.wallet import Wallet
from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.unit.helpers.mock_transactions import get_introduce_motion_tx, get_vote_tx, get_register_tx, get_approve_tx, get_vote_candidate_tx
from unittest import TestCase
import asyncio
import json
import random
import shutil
from tests.integration.mock.threaded_node import create_a_node
import pathlib
from tests.integration.mock.mock_data_structures import MockBlocks

class TestSingleNodeElectionsWithMetering(TestCase):
    def setUp(self) -> None:
        self.node_wallet = Wallet()
        self.tmp_storage = pathlib.Path().cwd().joinpath('temp_storage')

        self.blocks = MockBlocks(
            num_of_blocks=1,
            founder_wallet=self.node_wallet,
            initial_members={
                'masternodes': [
                    self.node_wallet.verifying_key
                ]
            }
        )
        self.genesis_block = self.blocks.get_block_by_index(index=0)

        self.threaded_node = create_a_node(node_wallet=self.node_wallet, genesis_block=self.genesis_block, metering=True, temp_storage_root=self.tmp_storage)

        self.threaded_node.start()
        while not self.threaded_node.node or not self.threaded_node.node.started or not self.threaded_node.node.network.running:
            self.await_async_process(asyncio.sleep, 0.1)

    def tearDown(self) -> None:
        self.await_async_process(self.threaded_node.stop)
        #shutil.rmtree(self.tmp_storage)

    def await_async_process(self, process, *args, **kwargs):
        tasks = asyncio.gather(
            process(*args, **kwargs)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def test_single_node_elections_with_metering(self):
        cands = [Wallet() for i in range(5)]
        self.threaded_node.set_smart_contract_value(f'currency.balances:{self.node_wallet.verifying_key}', 1000000)
        for c in cands:
            self.threaded_node.set_smart_contract_value(f'currency.balances:{c.verifying_key}', 1000000)

        for c in cands:
            self.threaded_node.send_tx(json.dumps(get_approve_tx(wallet=c, processor_vk=self.threaded_node.vk, to='elect_masternodes', stamps=200)).encode())
            self.await_async_process(asyncio.sleep, 1)
            self.threaded_node.send_tx(json.dumps(get_register_tx(wallet=c, processor_vk=self.threaded_node.vk, nonce=1, stamps=200)).encode())

        self.threaded_node.send_tx(json.dumps(get_introduce_motion_tx(policy='masternodes', motion=2, wallet=self.threaded_node.wallet, stamps=200)).encode())

        while self.threaded_node.block_storage.total_blocks() != 12:
            self.await_async_process(asyncio.sleep, 0.1)

        self.threaded_node.send_tx(
            json.dumps(
                get_vote_tx(
                    policy='masternodes', obj=['vote_on_motion', True],
                    wallet=self.node_wallet,
                    nonce=2,
                    stamps=200
                )
            ).encode()
        )

        while self.threaded_node.block_storage.total_blocks() != 13:
            self.await_async_process(asyncio.sleep, 0.1)

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

        random_master.send_tx(json.dumps(get_approve_tx(wallet=new_members_wallet, processor_vk=random_master.vk, to='elect_masternodes')).encode())
        random_master.send_tx(json.dumps(get_register_tx(wallet=new_members_wallet, processor_vk=random_master.vk, nonce=1)).encode())
        random_master.send_tx(json.dumps(get_introduce_motion_tx(policy='masternodes', motion=2, wallet=random_master.wallet, nonce=2)).encode())

        self.num_blocks_total += 3
        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        for i in range(self.num_yays_needed):
            self.network.masternodes[i].send_tx(
                json.dumps(
                    get_vote_tx(
                        policy='masternodes', obj=['vote_on_motion', True],
                        wallet=self.network.masternodes[i].wallet,
                        nonce=3
                    )
                ).encode()
            )

        self.num_blocks_total += self.num_yays_needed
        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.network.add_masternode(wallet=new_members_wallet)
        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.network.send_tx_to_masternode(random_master.vk); self.num_blocks_total += 1
        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.assertTrue(self.network.get_masternode(new_members_wallet.verifying_key).node_started)

    def test_multiple_candidates_winner_can_join_the_network(self):
        new_members_wallet = Wallet(); candidate_wallet = Wallet()
        self.fund_member(new_members_wallet); self.fund_member(candidate_wallet)
        random_master = random.choice(self.network.masternodes)

        for w in [candidate_wallet, new_members_wallet]:
            random_master.send_tx(
                json.dumps(get_approve_tx(wallet=w, processor_vk=random_master.vk,
                               to='elect_masternodes')).encode()
            )
            random_master.send_tx(
                json.dumps(get_register_tx(wallet=w, processor_vk=random_master.vk, nonce=1)).encode()
            )

        self.num_blocks_total += 4

        voters = [Wallet(), Wallet()]
        for voter in voters:
            self.fund_member(voter)
            random_master.send_tx(
                json.dumps(get_approve_tx(wallet=voter, processor_vk=random_master.vk,
                               to='elect_masternodes', amount=10)).encode()
            )
            random_master.send_tx(
                json.dumps(get_vote_candidate_tx(wallet=voter, processor_vk=random_master.vk,
                    candidate=new_members_wallet.verifying_key,
                    nonce=1)).encode()
            )

        self.num_blocks_total += 4

        random_master.send_tx(
            json.dumps(get_introduce_motion_tx(policy='masternodes', motion=2, wallet=random_master.wallet, nonce=2)).encode()
        ); self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        for i in range(self.num_yays_needed):
            self.network.masternodes[i].send_tx(
                json.dumps(
                    get_vote_tx(
                        policy='masternodes', obj=['vote_on_motion', True],
                        wallet=self.network.masternodes[i].wallet,
                        nonce=3
                    )
                ).encode()
            )

        self.num_blocks_total += self.num_yays_needed
        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        for node in self.network.all_nodes:
            self.assertIn(new_members_wallet.verifying_key, node.get_smart_contract_value('masternodes.S:members'))
            self.assertNotIn(candidate_wallet.verifying_key, node.get_smart_contract_value('masternodes.S:members'))

        self.network.add_masternode(wallet=new_members_wallet)
        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.network.send_tx_to_masternode(random_master.vk); self.num_blocks_total += 1
        self.network.await_all_nodes_done_processing(block_height=self.num_blocks_total)

        self.assertTrue(self.network.get_masternode(new_members_wallet.verifying_key).node_started)
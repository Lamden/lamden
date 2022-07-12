from lamden import contracts
from pathlib import Path
from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.integration.mock.mock_data_structures import MockBlocks
from tests.unit.helpers.mock_transactions import get_introduce_motion_tx, get_vote_tx, get_new_currency_tx
from unittest import TestCase
import copy
import json

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNewNodeCatchup(TestCase):
    def setUp(self):
        try:
            self.loop = asyncio.get_event_loop()

            if self.loop.is_closed():
                self.loop = None
        except:
            self.loop = None
        finally:
            if not self.loop:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

        self.network = LocalNodeNetwork(
            genesis_path=Path(f'{Path.cwd()}/mock')
        )

    def tearDown(self):
        task = asyncio.ensure_future(self.network.stop_all_nodes())
        while not task.done():
            self.loop.run_until_complete(asyncio.sleep(0.1))

        if not self.loop.is_closed():
            self.loop.stop()
            self.loop.close()

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def add_blocks_to_network(self, num_of_blocks):
        new_blocks = copy.copy(MockBlocks(num_of_blocks=num_of_blocks))
        for i in range(num_of_blocks):
            block_num = i + 1

            for tn in self.network.all_nodes:
                new_block = new_blocks.get_block(num=block_num)
                tn.node.blocks.store_block(block=copy.deepcopy(new_block))
                tn.node.update_block_db(block=new_block)
                tn.node.apply_state_changes_from_block(block=new_block)
        return new_blocks

    def test_new_peer_can_catchup_blocks_to_block_height_of_highest_node_block_height(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=1
        )

        blocks = self.add_blocks_to_network(num_of_blocks=5)

        self.network.add_new_node_to_network(
            node_type="delegate"
        )

        existing_node = self.network.masternodes[0]
        new_node = self.network.delegates[1]

        self.async_sleep(5)

        blocks.add_block()
        new_block = blocks.get_block(num=6)
        new_node.node.last_minted_block = new_block

        self.async_sleep(5)

        self.assertEqual(existing_node.latest_block_height, new_node.latest_block_height)

    def test_new_node_state_is_the_same_as_peers_after_catchup(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=1
        )

        blocks = self.add_blocks_to_network(num_of_blocks=5)

        self.network.add_new_node_to_network(
            node_type="delegate"
        )

        new_node = self.network.delegates[1]

        self.async_sleep(5)

        blocks.add_block()
        new_block = blocks.get_block(num=6)
        new_node.node.last_minted_block = new_block
        new_node.node.apply_state_changes_from_block(block=new_block)

        self.async_sleep(5)

        for vk, amount in blocks.internal_state.items():
            state_amount = new_node.get_smart_contract_value(key=f'currency.balances:{vk}')
            self.assertEqual(amount, state_amount)

class TestNodeLeaving(TestCase):
    def setUp(self):
        self.network = LocalNodeNetwork(
            genesis_path=Path(contracts.__path__[0])
        )

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

    def test_node_kick_out_updates_state_and_shuts_down_kicked_node(self):
        self.network.create_new_network(num_of_masternodes=3)

        exile = self.network.masternodes[0]
        voters = [self.network.masternodes[1], self.network.masternodes[2]]

        introduce_motion_remove_member_tx = get_introduce_motion_tx(
            policy='masternodes', motion=1, vk=exile.vk, wallet=voters[0].node.wallet
        )
        voters[0].send_tx(json.dumps(introduce_motion_remove_member_tx).encode())

        for voter in voters:
            vote_yay_tx = get_vote_tx(policy='masternodes', vote=True, wallet=voter.node.wallet, nonce=1)
            voter.send_tx(json.dumps(vote_yay_tx).encode())

        self.network.await_all_nodes_done_processing(block_height=3)

        expected_members = [voter.vk for voter in voters]
        for voter in voters:
            self.assertListEqual(voter.get_smart_contract_value('masternodes.S:members'), expected_members)
            self.assertEqual(voter.network.num_of_peers(), 1)
        self.assertFalse(exile.node_is_running)

    def test_node_kick_out_clears_results_from_kicked_peer(self):
        self.network.create_new_network(num_of_masternodes=3)
        for node in self.network.all_nodes:
            self.assertTrue(node.node_is_running)
            node.set_smart_contract_value(
                key=f'currency.balances:{self.network.founders_wallet.verifying_key}',
                value=1000000
            )
        for node in self.network.all_nodes:
            self.await_async_process(node.node.pause_validation_queue)

        exile = self.network.masternodes[0]
        voters = [self.network.masternodes[1], self.network.masternodes[2]]

        introduce_motion_remove_member_tx = get_introduce_motion_tx(
            policy='masternodes', motion=1, vk=exile.vk, wallet=voters[0].node.wallet
        )
        voters[0].send_tx(json.dumps(introduce_motion_remove_member_tx).encode())

        for voter in voters:
            vote_yay_tx = get_vote_tx(policy='masternodes', vote=True, wallet=voter.node.wallet, nonce=1)
            voter.send_tx(json.dumps(vote_yay_tx).encode())

        # TODO: should legit nodes eventually not process this TX?
        exile.send_tx(
            json.dumps(get_new_currency_tx(wallet=self.network.founders_wallet, processor=exile.vk)).encode()
        )

        for node in self.network.all_nodes:
            while len(node.validation_queue) != 4:
                self.await_async_process(asyncio.sleep, 0.1)
            while node.current_height != 2:
                self.await_async_process(node.validation_queue.process_next)

        last_hlc = exile.validation_queue[-1]
        for node in self.network.all_nodes:
            # Assert results from exile node are present before we process 3rd TX
            self.assertIsNotNone(
                node.validation_queue.validation_results[last_hlc]['solutions'].get(exile.wallet.verifying_key, None)
            )
            while node.current_height != 3:
                self.await_async_process(node.validation_queue.process_next)
            if node != exile:
                # Assert TX number 3 has cleared the results from exile node
                self.assertIsNone(
                    node.validation_queue.validation_results[last_hlc]['solutions'].get(exile.wallet.verifying_key, None)
                )
                node.node.unpause_all_queues()

        self.network.await_all_nodes_done_processing(block_height=4, nodes=voters)

        expected_members = [voter.vk for voter in voters]
        for voter in voters:
            self.assertListEqual(voter.get_smart_contract_value('masternodes.S:members'), expected_members)
            self.assertEqual(voter.network.num_of_peers(), 1)
        self.assertFalse(exile.node_is_running)
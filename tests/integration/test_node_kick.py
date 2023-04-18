from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.unit.helpers.mock_transactions import get_introduce_motion_tx, get_vote_tx, get_new_currency_tx
from unittest import TestCase
import asyncio
import json
import random

class TestNodeKick(TestCase):
    def setUp(self):
        self.network = LocalNodeNetwork(
            num_of_masternodes=5
        )

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        while not self.network.all_nodes_started:
            self.loop.run_until_complete(asyncio.sleep(1))

        self.exile = self.network.masternodes[-1]
        self.voters = self.network.masternodes[:-1]
        self.num_yays_needed = len(self.network.all_nodes) // 2 + 1
        self.fund_founder()

    def tearDown(self):
        task = asyncio.ensure_future(self.network.stop_all_nodes())

        while not task.done():
            self.loop.run_until_complete(asyncio.sleep(0.1))

        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def await_async_process(self, process, *args, **kwargs):
        tasks = asyncio.gather(
            process(*args, **kwargs)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def fund_founder(self):
        for node in self.network.all_nodes:
            node.set_smart_contract_value(
                key=f'currency.balances:{self.network.founders_wallet.verifying_key}',
                value=1000000
            )

    def test_updates_state_and_shuts_down_kicked_node(self):
        random_voter = random.choice(self.voters)
        introduce_motion_remove_member_tx = get_introduce_motion_tx(
            policy='masternodes', motion=1, vk=self.exile.vk, wallet=random_voter.node.wallet
        )
        random_voter.send_tx(json.dumps(introduce_motion_remove_member_tx).encode())

        self.network.await_all_nodes_done_processing(block_height=2)

        for voter in self.voters[:self.num_yays_needed]:
            vote_yay_tx = get_vote_tx(policy='masternodes', obj=['vote_on_motion', True], wallet=voter.node.wallet, nonce=1)
            voter.send_tx(json.dumps(vote_yay_tx).encode())

        self.network.await_all_nodes_done_processing(block_height=self.num_yays_needed + 2)

        expected_members = [voter.vk for voter in self.voters]
        for voter in self.voters:
            self.assertListEqual(voter.get_smart_contract_value('masternodes.S:members'), expected_members)
            self.assertEqual(voter.network.num_of_peers(), len(self.voters) - 1)
        self.assertFalse(self.exile.node_is_running)

    def test_nodes_clear_results_from_kicked_peer(self):
        for node in self.network.all_nodes:
            self.await_async_process(node.node.pause_validation_queue)

        random_voter = random.choice(self.voters)
        introduce_motion_remove_member_tx = get_introduce_motion_tx(
            policy='masternodes', motion=1, vk=self.exile.vk, wallet=random_voter.node.wallet
        )
        random_voter.send_tx(json.dumps(introduce_motion_remove_member_tx).encode())

        self.await_async_process(asyncio.sleep, 1)

        for voter in self.voters[:self.num_yays_needed]:
            vote_yay_tx = get_vote_tx(policy='masternodes', obj=['vote_on_motion', True], wallet=voter.node.wallet, nonce=1)
            voter.send_tx(json.dumps(vote_yay_tx).encode())
            self.await_async_process(asyncio.sleep, 1)

        random_voter.send_tx(
            json.dumps(get_new_currency_tx(wallet=self.network.founders_wallet, processor=random_voter.vk, nonce=2)).encode()
        )

        num_tx_total = self.num_yays_needed + 2
        for node in self.network.all_nodes:
            while len(node.validation_queue) != num_tx_total:
                self.await_async_process(asyncio.sleep, 0.1)
            while node.blocks.total_blocks() != num_tx_total - 1:
                self.await_async_process(node.validation_queue.process_next)

        last_hlc = self.exile.validation_queue[-1]
        for node in self.network.all_nodes:
            # Assert results from exile node are present before we process last TX which will pass the motion
            self.assertIsNotNone(
                node.validation_queue.validation_results[last_hlc]['solutions'].get(self.exile.wallet.verifying_key, None)
            )
            while node.blocks.total_blocks() != num_tx_total:
                self.await_async_process(node.validation_queue.process_next)
            if node != self.exile:
                # Assert last vote TX passed the motion thus removing older results from exile
                self.assertIsNone(
                    node.validation_queue.validation_results[last_hlc]['solutions'].get(self.exile.wallet.verifying_key, None)
                )
                node.node.unpause_all_queues()

        self.network.await_all_nodes_done_processing(block_height=num_tx_total + 1, nodes=self.voters)

        expected_members = [voter.vk for voter in self.voters]
        for voter in self.voters:
            self.assertListEqual(voter.get_smart_contract_value('masternodes.S:members'), expected_members)
            self.assertEqual(voter.network.num_of_peers(), len(self.voters) - 1)
        self.assertFalse(self.exile.node_is_running)

    def test_nodes_drop_tx_if_processor_was_kicked(self):
        random_voter = random.choice(self.voters)
        introduce_motion_remove_member_tx = get_introduce_motion_tx(
            policy='masternodes', motion=1, vk=self.exile.vk, wallet=random_voter.node.wallet
        )
        random_voter.send_tx(json.dumps(introduce_motion_remove_member_tx).encode())

        self.network.await_all_nodes_done_processing(block_height=2)

        for voter in self.voters[:self.num_yays_needed]:
            vote_yay_tx = get_vote_tx(policy='masternodes', obj=['vote_on_motion', True], wallet=voter.node.wallet, nonce=1)
            voter.send_tx(json.dumps(vote_yay_tx).encode())

        # This TX shouldn't eventually be processed since it is coming from exile.
        self.exile.send_tx(
            json.dumps(get_new_currency_tx(wallet=self.network.founders_wallet, processor=self.exile.vk)).encode()
        )

        num_tx_total = self.num_yays_needed + 1
        self.network.await_all_nodes_done_processing(block_height=num_tx_total + 2, nodes=self.voters)

        expected_members = [voter.vk for voter in self.voters]
        for voter in self.voters:
            self.assertListEqual(voter.get_smart_contract_value('masternodes.S:members'), expected_members)
            self.assertEqual(voter.network.num_of_peers(), len(self.voters) - 1)
        self.assertFalse(self.exile.node_is_running)
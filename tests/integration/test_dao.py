from lamden.crypto.wallet import Wallet
from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.unit.helpers.mock_transactions import get_vote_tx
from unittest import TestCase
import asyncio
import json
import random
from contracting.stdlib.bridge.time import Datetime
from datetime import datetime as dt, timedelta as td

class TestDAO(TestCase):
    def setUp(self):
        self.network = LocalNodeNetwork(
            num_of_masternodes=5
        )

        loop = asyncio.get_event_loop()
        while not self.network.all_nodes_started:
            loop.run_until_complete(asyncio.sleep(1))

        self.num_votes_needed = len(self.network.all_nodes) * 3 // 5 + 1
        self.num_specific_votes_needed = self.num_votes_needed * 7 // 10 + 1
        self.num_blocks_total = 1

        self.recipient_vk = Wallet().verifying_key
        self.amount = 100_000

    def tearDown(self):
        task = asyncio.ensure_future(self.network.stop_all_nodes())
        loop = asyncio.get_event_loop()
        while not task.done():
            loop.run_until_complete(asyncio.sleep(0.1))

    def test_can_introduce_motion(self):
        random_member = random.choice(self.network.masternodes)

        random_member.send_tx(
            json.dumps(
                get_vote_tx(wallet=random_member.wallet, policy='dao', obj=[self.recipient_vk, self.amount])
            ).encode()
        ); self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(self.num_blocks_total)

        for node in self.network.all_nodes:
            self.assertEqual(node.get_smart_contract_value(key='dao.S:recipient_vk'), self.recipient_vk)
            self.assertEqual(node.get_smart_contract_value(key='dao.S:amount'), self.amount)
            self.assertIsNotNone(node.get_smart_contract_value(key='dao.S:motion_start'))

    def test_motion_passes_after_delay_if_sufficient_amount_of_positive_votes(self):
        # Introduce motion
        random_member = random.choice(self.network.masternodes)
        random_member.send_tx(
            json.dumps(
                get_vote_tx(wallet=random_member.wallet, policy='dao', obj=[self.recipient_vk, self.amount])
            ).encode()
        ); self.num_blocks_total += 1

        # Submit sufficient amount of specific votes. In this case: yays
        for i in range(self.num_specific_votes_needed):
            node = self.network.all_nodes[i]; nonce = 0 if node.vk != random_member.vk else 1
            node.send_tx(
                json.dumps(
                    get_vote_tx(wallet=node.wallet, policy='dao', obj=[True], nonce=nonce)
                ).encode()
            ); self.num_blocks_total += 1

        # Assert expected amount of yays
        self.network.await_all_nodes_done_processing(self.num_blocks_total)
        for node in self.network.all_nodes:
            self.assertEqual(node.get_smart_contract_value(key='dao.S:yays'), self.num_specific_votes_needed)

        # Submit rest of the needed votesd
        for i in range(self.num_specific_votes_needed, self.num_votes_needed):
            node = self.network.all_nodes[i]; nonce = 0 if node.vk != random_member.vk else 1
            node.send_tx(
                json.dumps(
                    get_vote_tx(wallet=node.wallet, policy='dao', obj=[False], nonce=nonce)
                ).encode()
            ); self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(self.num_blocks_total)

        # Assert motion was passed meaning pending_motion entry was created
        for node in self.network.all_nodes:
            pending_motions = node.get_smart_contract_value('dao.S:pending_motions')
            self.assertEqual(len(pending_motions), 1)
            self.assertIsNotNone(pending_motions[0]['motion_passed'])
            self.assertEqual(pending_motions[0]['recipient_vk'], self.recipient_vk)
            self.assertEqual(pending_motions[0]['amount'], self.amount)

            # Modify 'motion_passed' timestamp by hand so that it's finalized when next TX is sent
            pending_motions[0]['motion_passed'] = Datetime._from_datetime(dt.today() - td(days=2))
            node.contract_driver.set(key='dao.S:pending_motions', value=pending_motions)
            node.contract_driver.commit()

            # Fund dao balance so that transfer is successfull
            node.set_smart_contract_value(key=f'currency.balances:dao', value=100_000_000)

        # Send empty vote transaction which should finalize the motion
        random_member.send_tx(
            json.dumps(
                get_vote_tx(wallet=random_member.wallet, policy='dao', obj=[], nonce=2)
            ).encode()
        ); self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(self.num_blocks_total)

        # Assert motion was finalized
        for node in self.network.all_nodes:
            self.assertEqual(len(node.get_smart_contract_value('dao.S:pending_motions')), 0)
            self.assertEqual(node.get_smart_contract_value(f'currency.balances:{self.recipient_vk}'), self.amount)
            self.assertEqual(node.get_smart_contract_value(f'currency.balances:dao'), 100_000_000 - self.amount)

    def test_motion_reset_if_sufficient_amount_of_nay_votes(self):
        random_member = random.choice(self.network.masternodes)
        random_member.send_tx(
            json.dumps(
                get_vote_tx(wallet=random_member.wallet, policy='dao', obj=[self.recipient_vk, self.amount])
            ).encode()
        ); self.num_blocks_total += 1

        for i in range(self.num_specific_votes_needed):
            node = self.network.all_nodes[i]; nonce = 0 if node.vk != random_member.vk else 1
            node.send_tx(
                json.dumps(
                    get_vote_tx(wallet=node.wallet, policy='dao', obj=[False], nonce=nonce)
                ).encode()
            ); self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(self.num_blocks_total)
        for node in self.network.all_nodes:
            self.assertEqual(node.get_smart_contract_value(key='dao.S:nays'), self.num_specific_votes_needed)

        for i in range(self.num_specific_votes_needed, self.num_votes_needed):
            node = self.network.all_nodes[i]; nonce = 0 if node.vk != random_member.vk else 1
            node.send_tx(
                json.dumps(
                    get_vote_tx(wallet=node.wallet, policy='dao', obj=[True], nonce=nonce)
                ).encode()
            ); self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(self.num_blocks_total)

        # Assert dao contract state was reset to zeros
        for node in self.network.all_nodes:
            self.assertEqual(len(node.get_smart_contract_value('dao.S:pending_motions')), 0)
            self.assertEqual(node.get_smart_contract_value(key='dao.S:yays'), 0)
            self.assertEqual(node.get_smart_contract_value(key='dao.S:nays'), 0)
            self.assertIsNone(node.get_smart_contract_value(key='dao.S:recipient_vk'))
            self.assertIsNone(node.get_smart_contract_value(key='dao.S:amount'))
            self.assertIsNone(node.get_smart_contract_value(key='dao.S:motion_start'))

    def test_motion_is_reset_if_exceeded_delay(self):
        # Introduce motion
        random_member = random.choice(self.network.masternodes)
        random_member.send_tx(
            json.dumps(
                get_vote_tx(wallet=random_member.wallet, policy='dao', obj=[self.recipient_vk, self.amount])
            ).encode()
        ); self.num_blocks_total += 1

        # Deprecate this motion
        for node in self.network.all_nodes:
            node.contract_driver.set(key='dao.S:motion_start', value=Datetime._from_datetime(dt.today() - td(days=2)))
            node.contract_driver.commit()

        # Send empty vote transaction which should finalize the motion
        random_member.send_tx(
            json.dumps(
                get_vote_tx(wallet=random_member.wallet, policy='dao', obj=[random.choice([True, False])], nonce=1)
            ).encode()
        ); self.num_blocks_total += 1

        self.network.await_all_nodes_done_processing(self.num_blocks_total)

        # Assert dao contract state was reset to zeros
        for node in self.network.all_nodes:
            self.assertEqual(len(node.get_smart_contract_value('dao.S:pending_motions')), 0)
            self.assertEqual(node.get_smart_contract_value(key='dao.S:yays'), 0)
            self.assertEqual(node.get_smart_contract_value(key='dao.S:nays'), 0)
            self.assertIsNone(node.get_smart_contract_value(key='dao.S:recipient_vk'))
            self.assertIsNone(node.get_smart_contract_value(key='dao.S:amount'))
            self.assertIsNone(node.get_smart_contract_value(key='dao.S:motion_start'))

from unittest import TestCase

from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
from contracting.execution.executor import Executor

from lamden import storage
from lamden import rewards
from lamden.nodes import processing_queue
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock

def createMockTx():
    return {
        'metadata': {
            'signature': '7eac4c17004dced6d079e260952fffa7750126d5d2c646ded886e6b1ab4f6da1e22f422aad2e1954c9529cfa71a043af8c8ef04ccfed6e34ad17c6199c0eba0e',
            'timestamp': 1624049397
        },
        'payload': {
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': {'__fixed__': '499950'},
                'to': '6e4f96fa89c508d2842bef3f7919814cd1f64c16954d653fada04e61cc997206'},
                'nonce': 0,
                'processor': '92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e',
            'sender': 'd48b174f71efb9194e9cd2d58de078882bd172fcc7c8ac5ae537827542ae604e',
            'stamps_supplied': 100
        }
    }

class TestProcessingQueue(TestCase):

    def setUp(self):
        self.driver = ContractDriver()
        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=''
        )
        self.wallet = Wallet()

        self.executor = Executor(driver=self.driver)
        self.reward_manager = rewards.RewardManager()

        self.hlc_clock = HLC_Clock()
        self.processing_delay_secs = {
            'base': 0.75,
            'self': 0.75
        }

        self.running = True

        self.current_height = lambda: storage.get_latest_block_height(self.driver)
        self.current_hash = lambda: storage.get_latest_block_hash(self.driver)

        self.main_processing_queue = processing_queue.ProcessingQueue(
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=self.processing_delay_secs,
            executor=self.executor,
            get_current_hash=self.current_hash,
            get_current_height=self.current_height,
            stop_node=self.stop,
            reward_manager=self.reward_manager
        )

        self.client.flush()

    def tearDown(self):
        self.main_processing_queue.stop()
        self.main_processing_queue.flush()

    def stop(self):
        self.running = False

    def test_add_tx_to_queue(self):
        self.main_processing_queue.append(tx=createMockTx())
        self.assertEqual(len(self.main_processing_queue), 1)

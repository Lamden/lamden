from unittest import TestCase
import shutil
from pathlib import Path

from lamden.nodes.base import Node

from lamden.storage import BlockStorage, NonceStorage, set_latest_block_height
from contracting.db.driver import ContractDriver, FSDriver, InMemDriver
from lamden.nodes.filequeue import FileQueue
from lamden.utils import hlc
from lamden.crypto.wallet import Wallet

from tests.integration.mock.mock_data_structures import MockBlocks
from tests.unit.helpers.mock_transactions import get_processing_results, get_tx_message
from lamden.cli.start import resolve_genesis_block

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestBaseNode_HardApply(TestCase):
    def setUp(self):
        self.current_path = Path.cwd()
        self.genesis_path = Path(f'{self.current_path.parent}/integration/mock')
        self.temp_storage = Path(f'{self.current_path}/temp_storage')



        try:
            shutil.rmtree(self.temp_storage)
        except FileNotFoundError:
            pass
        self.temp_storage.mkdir(exist_ok=True, parents=True)

        self.node_wallet = Wallet()
        self.mock_blocks = MockBlocks(num_of_blocks=5, one_wallet=True,
                                      initial_members=[self.node_wallet.verifying_key])
        self.genesis_block = self.mock_blocks.get_block_by_index(0)

        self.node: Node = self.create_node_instance()


    def tearDown(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.stop())

        del self.node

    def create_node_instance(self) -> Node:
        node_dir = Path(f'{self.temp_storage}/{self.node_wallet.verifying_key}')
        # node_state_dir = Path(f'{node_dir}/state')
        raw_driver = InMemDriver()
        contract_driver = ContractDriver(driver=raw_driver)
        block_storage = BlockStorage(root=node_dir)
        nonce_storage = NonceStorage(nonce_collection=Path(node_dir).joinpath('nonces'))

        tx_queue = FileQueue(root=node_dir)

        constitution = {
            'masternodes': {self.node_wallet.verifying_key: 'tcp://127.0.0.1:19000'},
            'delegates': {},
        }

        return Node(
            constitution=constitution,
            bootnodes={},
            socket_base="",
            wallet=self.node_wallet,
            socket_ports=self.create_socket_ports(index=0),
            driver=contract_driver,
            blocks=block_storage,
            tx_queue=tx_queue,
            testing=True,
            nonces=nonce_storage,
            genesis_block=self.genesis_block,
        )

    def start_node(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.start())

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def get_state_changes_from_processing_results(self, processing_results: dict) -> list:
        try:
            return processing_results['tx_result'].get('state', [])
        except Exception:
            return []

    def test_can_create_node_instance(self):
        self.assertIsNotNone(self.node)

    def test_can_start_node_instance(self):
        try:
            self.start_node()
        except Exception as err:
            self.fail('Node should not throw exceptions on startup')

        self.assertTrue(self.node.running)

    def test_hard_apply_block_finish__does_not_set_last_hlc_in_consensus_if_less_than_current(self):
        block = self.mock_blocks.get_block_by_index(1)

        new_timestamp = self.node.hlc_clock.get_new_hlc_timestamp()
        self.node.validation_queue.last_hlc_in_consensus = new_timestamp

        self.node.hard_apply_block_finish(block=block)
        self.assertEqual(new_timestamp, self.node.validation_queue.last_hlc_in_consensus)

    def test_hard_apply_store_block__can_store_a_block(self):
        block = self.mock_blocks.get_block_by_index(1)
        self.node.hard_apply_store_block(block=block)

        self.assertEqual(block.get('number'), self.node.get_current_height())
        self.assertEqual(block.get('hash'), self.node.get_current_hash())
        self.assertEqual(2, self.node.blocks.total_blocks())

    def test_hard_apply_store_block__stores_in_holding_during_catchup(self):
        self.node.hold_blocks = True
        block = self.mock_blocks.get_block_by_index(1)
        self.node.hard_apply_store_block(block=block)

        self.assertEqual(0, self.node.get_current_height())
        self.assertEqual(1, self.node.blocks.total_blocks())

        self.assertEqual(1, len(self.node.held_blocks))

    def test_hard_apply_processing_results__mints_block_from_processing_results_object(self):
        processing_results = get_processing_results()

        hlc_timestamp = processing_results.get('hlc_timestamp')
        expected_block_num = hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp)

        state_changes = self.get_state_changes_from_processing_results(processing_results)

        new_block = self.node.hard_apply_processing_results(processing_results=processing_results)

        self.assertIsNotNone(new_block)
        self.assertEqual(expected_block_num, self.node.get_current_height())
        self.assertEqual(2, self.node.blocks.total_blocks())


        # Validate the state was hard applied
        for state_change in state_changes:
            key = state_change.get('key')
            value = state_change.get('value')

            driver_value = self.node.driver.driver.get(item=key)
            self.assertIsNotNone(driver_value)
            self.assertEqual(value, driver_value)

    def test_hard_apply_processing_results__hard_applies_state_from_driver_if_consensus_matches_me(self):
        class HardApply:
            def __init__(self):
                self.was_called = False

            def hard_apply(self, hlc):
                self.was_called = hlc


        mock_hard_apply = HardApply()
        self.node.driver.hard_apply = mock_hard_apply.hard_apply


        processing_results = get_processing_results()
        hlc_timestamp = processing_results.get('hlc_timestamp')

        self.node.validation_queue.validation_results[hlc_timestamp] = {}
        self.node.validation_queue.validation_results[hlc_timestamp]['solutions'] = {}
        self.node.validation_queue.validation_results[hlc_timestamp]['solutions'][self.node.wallet.verifying_key] = \
            processing_results['tx_result']['hash']

        self.node.hard_apply_processing_results(processing_results=processing_results)

        self.assertEqual(hlc_timestamp, mock_hard_apply.was_called)

    def test_hard_apply_processing_results__hard_applies_state_from_block_if_not_matches_me(self):
        class HardApply:
            def __init__(self):
                self.was_called = False

            def apply_state_changes_from_block(self, block):
                self.was_called = block.get('hlc_timestamp')


        mock_hard_apply = HardApply()
        self.node.apply_state_changes_from_block = mock_hard_apply.apply_state_changes_from_block

        processing_results = get_processing_results()
        hlc_timestamp = processing_results.get('hlc_timestamp')

        self.node.validation_queue.validation_results[hlc_timestamp] = {}
        self.node.validation_queue.validation_results[hlc_timestamp]['solutions'] = {}

        self.node.hard_apply_processing_results(processing_results=processing_results)

        self.assertEqual(hlc_timestamp, mock_hard_apply.was_called)

    def test_hard_apply_has_later_blocks__can_reorder_blocks_when_given_an_earlier_block(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.hard_apply_block(block=self.mock_blocks.get_block_by_index(index=2)))
        loop.run_until_complete(self.node.hard_apply_block(block=self.mock_blocks.get_block_by_index(index=3)))
        loop.run_until_complete(self.node.hard_apply_block(block=self.mock_blocks.get_block_by_index(index=4)))

        self.assertEqual(4, self.node.blocks.total_blocks())

        early_block = self.mock_blocks.get_block_by_index(1)

        early_block_hlc_timestamp = early_block.get('hlc_timestamp')

        # Get any blocks that have been committed that are later than this hlc_timestamp
        later_blocks = self.node.blocks.get_later_blocks(hlc_timestamp=early_block_hlc_timestamp)

        self.assertEqual(3, len(later_blocks))

        self.node.driver.driver.set(f'currency.balances:{self.mock_blocks.receiver_wallet.verifying_key}', 0)

        self.node.hard_apply_has_later_blocks(later_blocks=later_blocks, block=early_block)

        self.assertEqual(5, self.node.blocks.total_blocks())

        receiver_amount = self.node.driver.get(f'currency.balances:{self.mock_blocks.receiver_wallet.verifying_key}')
        expected_amount = 10.5 * 4
        self.assertEqual(expected_amount, receiver_amount)

    def test_hard_apply_has_later_blocks__can_reorder_blocks_when_given_earlier_processing_results(self):
        tx_amount = "10.5"
        tx_message = get_tx_message(
            to=self.mock_blocks.receiver_wallet.verifying_key,
            amount=tx_amount,
            wallet=self.mock_blocks.founder_wallet,
            hlc_timestamp='1970-01-01T01:01:01.000000000Z_0'
        )

        self.node.driver.driver.set(
            f'currency.balances:{self.mock_blocks.founder_wallet.verifying_key}',
            {"__fixed__": "10.5"}

        )

        processing_results = get_processing_results(tx_message=tx_message, driver=self.node.driver)
        early_processing_results_hlc_timestamp = processing_results.get('hlc_timestamp')

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.hard_apply_block(block=self.mock_blocks.get_block_by_index(index=2)))
        loop.run_until_complete(self.node.hard_apply_block(block=self.mock_blocks.get_block_by_index(index=3)))
        loop.run_until_complete(self.node.hard_apply_block(block=self.mock_blocks.get_block_by_index(index=4)))

        self.assertEqual(4, self.node.blocks.total_blocks())

        # Get any blocks that have been committed that are later than this hlc_timestamp
        later_blocks = self.node.blocks.get_later_blocks(hlc_timestamp=early_processing_results_hlc_timestamp)

        self.assertEqual(3, len(later_blocks))

        self.node.driver.driver.set(f'currency.balances:{self.mock_blocks.receiver_wallet.verifying_key}', 0)

        self.node.hard_apply_has_later_blocks(later_blocks=later_blocks, processing_results=processing_results)

        self.assertEqual(5, self.node.blocks.total_blocks())

        receiver_amount = self.node.driver.get(f'currency.balances:{self.mock_blocks.receiver_wallet.verifying_key}')
        expected_amount = 10.5 * 4
        self.assertEqual(expected_amount, receiver_amount)

    def test_hard_apply_block__from_genesis_block(self):
        block = self.mock_blocks.get_block_by_index(0)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.hard_apply_block(block=block))

        founder_amount = self.node.driver.get(f'currency.balances:{self.mock_blocks.founder_wallet.verifying_key}')
        expected_amount = 100000000
        self.assertEqual(expected_amount, founder_amount)

    def test_apply_state_changes_from_block__from_genesis_block(self):
        block = self.mock_blocks.get_block_by_index(0)
        self.node.apply_state_changes_from_block(block=block)

        founder_amount = self.node.driver.get(f'currency.balances:{self.mock_blocks.founder_wallet.verifying_key}')
        expected_amount = 100000000

        self.assertEqual(expected_amount, founder_amount)

    def test_apply_state_changes_from_block__from_regular_block(self):
        block = self.mock_blocks.get_block_by_index(1)
        self.node.apply_state_changes_from_block(block=block)

        founder_amount = self.node.driver.get(f'currency.balances:{self.mock_blocks.receiver_wallet.verifying_key}')
        expected_amount = '10.5'

        self.assertEqual(expected_amount, str(founder_amount))

    def test_get_state_changes_from_block__returns_state_changes_from_genesis_block(self):
        gen_block = self.mock_blocks.get_block_by_index(0)
        state_changes = self.node.get_state_changes_from_block(block=gen_block)
        self.assertIsNotNone(state_changes)
        self.assertIsInstance(state_changes, list)
        self.assertEqual(92, len(state_changes))

    def test_get_state_changes_from_block__returns_state_changes_from_regular_block(self):
        block = self.mock_blocks.get_block_by_index(1)
        state_changes = self.node.get_state_changes_from_block(block=block)
        self.assertIsNotNone(state_changes)
        self.assertIsInstance(state_changes, list)
        self.assertEqual(1, len(state_changes))

    def test_get_state_changes_from_block__returns_empty_list_if_exception(self):
        state_changes = self.node.get_state_changes_from_block(block={})
        self.assertIsNotNone(state_changes)
        self.assertIsInstance(state_changes, list)
        self.assertEqual(0, len(state_changes))

    def test_update_block_db__makes_driver_updates(self):
        block = self.mock_blocks.get_block_by_index(1)

        block_num = block.get('number')
        block_hash = block.get('hash')

        self.node.update_block_db(block=block)

        self.assertEqual(block_num, self.node.get_current_height())
        self.assertEqual(block_hash, self.node.get_current_hash())

    def test_update_block_db__does_not_make_driver_updates_if_earlier(self):
        block_1 = self.mock_blocks.get_block_by_index(1)
        block_2 = self.mock_blocks.get_block_by_index(2)

        block_num = block_2.get('number')
        block_hash = block_2.get('hash')

        self.node.update_block_db(block=block_2)
        self.node.update_block_db(block=block_1)

        self.assertEqual(block_num, self.node.get_current_height())
        self.assertEqual(block_hash, self.node.get_current_hash())
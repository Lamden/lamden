from contracting.db.driver import InMemDriver, ContractDriver
from lamden import storage
from lamden.crypto.canonical import tx_result_hash_from_tx_result_object
from lamden.crypto.wallet import Wallet
from pathlib import Path
from tests.integration.mock.mock_data_structures import MockBlocks
from tests.integration.mock.threaded_node import create_a_node, ThreadedNode
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_processing_results
from unittest import TestCase
import asyncio
import gc
import shutil
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNode(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.num_of_nodes = 0

        self.blocks = storage.BlockStorage()

        self.driver = ContractDriver(driver=InMemDriver())

        self.stu_wallet = Wallet()
        self.jeff_wallet = Wallet()
        self.archer_wallet = Wallet()
        self.oliver_wallet = Wallet()

        self.founder_wallet = Wallet()
        self.node_wallet = Wallet()
        self.blocks = MockBlocks(
            num_of_blocks=1,
            founder_wallet=self.founder_wallet,
            initial_members={
                'masternodes': [self.node_wallet.verifying_key]
            }
        )
        self.genesis_block = self.blocks.get_block_by_index(index=0)

        self.tn: ThreadedNode = None
        self.nodes = list()
        self.sent_to_network = dict()

        self.temp_storage_root = Path().cwd().joinpath('temp_network')
        if self.temp_storage_root.is_dir():
            shutil.rmtree(self.temp_storage_root)

    def tearDown(self):
        if self.tn.node.running:
            self.await_async_process(self.tn.stop)

        if not self.loop.is_closed():
            self.loop.stop()
            self.loop.close()

        if self.temp_storage_root.is_dir():
            shutil.rmtree(self.temp_storage_root)
        gc.collect()

    @property
    def node(self):
        if not self.tn:
            return None
        return self.tn.node

    def create_node(self):
        self.tn = create_a_node(
            node_wallet=self.node_wallet,
            genesis_block=self.genesis_block,
            temp_storage_root=self.temp_storage_root
        )

        self.tn.set_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}', 10000000)

    def start_node(self):
        self.tn.start()
        self.async_sleep(1)

        while not self.node or not self.node.started or not self.node.network.running:
            self.async_sleep(1)

    def create_and_start_node(self):
        self.create_node()
        self.start_node()

    def start_all_nodes(self):
        for node in self.nodes:
            self.await_async_process(node.start)

    def stop_node(self, node=None):
        if (node):
            self.await_async_process(node.stop)
        else:
            self.await_async_process(self.node.stop)

    def await_async_process(self, process):
        tasks = asyncio.gather(
            process()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def await_hard_apply_block(self, node, processing_results):
        tasks = asyncio.gather(
            node.hard_apply_block(processing_results=processing_results)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    async def delay_processing_await(self, func, delay):
        await asyncio.sleep(delay)
        if func:
            return await func()

    def await_async_process_next(self, node):
        tasks = asyncio.gather(
            self.delay_processing_await(node.main_processing_queue.process_next, 0.1),
        )
        loop = asyncio.get_event_loop()
        res =  loop.run_until_complete(tasks)
        print(res)
        return res[0]

    def process_a_tx(self, node, tx_message):
        processing_results = get_processing_results(node=node, tx_message=tx_message)
        hlc_timestamp = processing_results.get('hlc_timestamp')

        node.last_processed_hlc = hlc_timestamp
        node.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

        node.store_solution_and_send_to_network(processing_results=processing_results)

        self.async_sleep(0.01)

        return processing_results

    def mock_unpause_all_queues(self):
        pass

    def mock_store_solution_and_send_to_network(self, processing_results):
        hlc_timestamp = processing_results['hlc_timestamp']
        if self.sent_to_network.get(hlc_timestamp, None) is None:
            self.sent_to_network[hlc_timestamp] = []
        tx_result_hash = tx_result_hash_from_tx_result_object(
            tx_result=processing_results['tx_result'],
            hlc_timestamp=processing_results['hlc_timestamp'],
            rewards=processing_results['rewards']
        )
        self.sent_to_network[hlc_timestamp].append(tx_result_hash)

        # Call actual store_solution_and_send_to_network method
        self.node.actual_store_solution_and_send_to_network(processing_results=processing_results)

    def test_reprocessing__should_reprocess__early_tx_changes_state_of_future_transactions(self):
        # This will test where all transactions share keys
        # TX #2 and #3 would have created state but will have different state after #1 is reprocessed
        self.create_and_start_node()

        # stop the validation queue
        self.await_async_process(self.node.pause_validation_queue)

        stu_balance_before = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        tx_args = {
            'to': self.jeff_wallet.verifying_key,
            'wallet': self.stu_wallet,
            'amount': tx_amount
        }

        tx_message_1 = self.node.make_tx_message(tx=get_new_currency_tx(**tx_args))
        tx_message_2 = self.node.make_tx_message(tx=get_new_currency_tx(**tx_args))
        tx_message_3 = self.node.make_tx_message(tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        last_processed_hlc = self.tn.node.get_last_processed_hlc()

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)

        while self.tn.node.get_last_processed_hlc() != hlc_timestamp_3:
            self.async_sleep(0.1)

        # TEST That Stu sent Jeff two currency transactions
        stu_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        stu_balance_mid_delta = stu_balance_before - stu_balance_mid
        self.assertEqual(str(tx_amount * 2), str(stu_balance_mid_delta))

        jeff_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        self.assertEqual(str(tx_amount * 2), str(jeff_balance_mid))

        # Process TX#1 which is an earlier HLC and should kick off reprocessing
        self.node.main_processing_queue.append(tx=tx_message_1)

        while self.tn.node.main_processing_queue.detected_rollback == True:
            self.async_sleep(0.1)

        self.async_sleep(3)

        self.node.driver.hard_apply(hlc=hlc_timestamp_3)

        # TEST That after the new transaction Stu has now sent Jeff 3 currency transactions
        stu_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        stu_balance_delta = stu_balance_before - stu_balance_after
        self.assertEqual(str(tx_amount * 3), str(stu_balance_delta))

        jeff_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        self.assertEqual(str(tx_amount * 3), str(jeff_balance_after))

    def test_reprocessing__should_reprocess__earlier_tx_will_create_state_for_later_tx_to_complete(self):
        # This will test where TX #2 and #3 would fail due to no balance to send
        # TX #1 is the late tx and after reprocessing it will supply the balance for #2 and #3 to be successful

        self.create_and_start_node()

        # stop the validation queue
        self.await_async_process(self.node.pause_validation_queue)

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        stu_balance_before = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_message_1 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))

        # Send from Jeff to Archer
        tx_message_2 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        # Send from Archer to Jeff
        tx_message_3 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.archer_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)

        while self.tn.node.get_last_processed_hlc() != hlc_timestamp_3:
            self.async_sleep(0.1)

        # TEST That Jeff did not have the balance to Archer in TX#2 and Archer did not have the balance to send to Jeff
        # in TX#3

        # Stu has same balance
        stu_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        stu_balance_mid_delta = stu_balance_before - stu_balance_mid
        self.assertEqual(0, float(str(stu_balance_mid_delta)))

        # Jeff has no balance
        jeff_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        self.assertEqual(0, jeff_balance_mid)

        # Archer has no balance
        archer_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.archer_wallet.verifying_key}')
        self.assertEqual(0, archer_balance_mid)

        # Process TX#1 which is an earlier HLC and should kick off reprocessing
        self.node.main_processing_queue.append(tx=tx_message_1)

        while self.tn.node.main_processing_queue.detected_rollback == True:
            self.async_sleep(0.1)

        self.async_sleep(3)

        self.node.driver.hard_apply(hlc=hlc_timestamp_3)

        # TEST that after reprocessing TX#1 Jeff and Archer now had balances to send and the state reflects that
        stu_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        jeff_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        archer_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.archer_wallet.verifying_key}')

        self.assertEqual(tx_amount, stu_balance_before - stu_balance_after)
        self.assertEqual(tx_amount, jeff_balance_after)
        # This is 0 instead of None showing that Archer had a balance but sent all of it. None would show that he NEVER
        # had a balance (like in the mid tests)
        self.assertEqual(0, float(str(archer_balance_after)))

    def test_reprocessing__should_reprocess__reprocesing_causes_previously_completed_tx_to_now_fail(self):
        # This will test where TX #3 will initially have pending deltas because TX #1 gave it a balance
        # TX #2 will be the late tx and after reprocessing TX #3 will no longer not have the balance to send as TX #2
        # will have spent it

        self.create_and_start_node()

        # stop the validation queue
        self.await_async_process(self.node.pause_validation_queue)

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        stu_balance_before = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_message_1 = self.node.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=tx_amount
        ))

        # Send from Jeff to Archer
        tx_message_2 = self.node.make_tx_message(tx=get_new_currency_tx(
            wallet=self.jeff_wallet,
            to=self.archer_wallet.verifying_key,
            amount=tx_amount
        ))

        # Send from Jeff to Archer
        tx_message_3 = self.node.make_tx_message(tx=get_new_currency_tx(
            wallet=self.jeff_wallet,
            to=self.archer_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_1)
        self.node.main_processing_queue.append(tx=tx_message_3)

        while self.tn.node.get_last_processed_hlc() != hlc_timestamp_3:
            self.async_sleep(0.1)


        # TEST That Stue sent currency to Jeff and then Jeff sent that currency to Archer
        stu_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        stu_balance_mid_delta = stu_balance_before - stu_balance_mid
        self.assertEqual(str(tx_amount), str(stu_balance_mid_delta))

        # Jeff has no balance
        jeff_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        self.assertEqual(0, float(str(jeff_balance_mid)))

        # Archer has a balance
        archer_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.archer_wallet.verifying_key}')
        self.assertEqual(str(tx_amount), str(archer_balance_mid))

        # Process TX#1 which is an earlier HLC and should kick off reprocessing
        self.node.main_processing_queue.append(tx=tx_message_2)
        while self.tn.node.main_processing_queue.detected_rollback == True:
            self.async_sleep(0.1)

        self.async_sleep(3)

        self.node.driver.hard_apply(hlc=hlc_timestamp_3)

        # TEST that after reprocessing, Jeff no longer has a balance to complete TX#3 but instead Archer was sent
        # currency in TX#2
        stu_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        jeff_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        archer_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.archer_wallet.verifying_key}')

        self.assertEqual(str(tx_amount), str(stu_balance_before - stu_balance_after))
        self.assertEqual(0, float(str(jeff_balance_after)))
        self.assertEqual(str(tx_amount), str(archer_balance_after))

    def test_reprocessing__should_reprocess__should_send_updated_result_to_network(self):
        # This will validate the nodes sends out new results after reprocessing
        # TX #2 and #3 would have created state but will have different state after #1 is reprocessed
        sent_to_network = {}

        self.create_and_start_node()

        # stop the validation queue
        self.await_async_process(self.node.pause_validation_queue)

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        # Mock the node's store_solution_and_send_to_network function so we can see if it was called
        self.node.actual_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = self.mock_store_solution_and_send_to_network

        stu_balance_before = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        tx_args = {
            'to': self.jeff_wallet.verifying_key,
            'wallet': self.stu_wallet,
            'amount': tx_amount
        }

        tx_message_1 = self.node.make_tx_message(tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        tx_message_2 = self.node.make_tx_message(tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']

        tx_message_3 = self.node.make_tx_message(tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so that we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)

        while self.tn.node.get_last_processed_hlc() != hlc_timestamp_3:
            self.async_sleep(0.1)

        # TEST Stu and Jeff have expected balances after completed currency transactions
        stu_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        stu_balance_mid_delta = stu_balance_before - stu_balance_mid
        self.assertEqual(str(tx_amount * 2), str(stu_balance_mid_delta))

        # Jeff has no balance
        jeff_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        self.assertEqual(str(tx_amount * 2), str(jeff_balance_mid))

        # Process TX#1 which is an earlier HLC and should kick off reprocessing
        self.node.main_processing_queue.append(tx=tx_message_1)

        while self.tn.node.main_processing_queue.detected_rollback == True:
            self.async_sleep(0.1)

        self.async_sleep(3)

        self.node.driver.hard_apply(hlc=hlc_timestamp_3)

        # TEST TX#2 and TX#3 sent two different results to the network because the results where different after
        # reprocessing
        self.assertEqual(2, len(self.sent_to_network[hlc_timestamp_2]))
        self.assertNotEqual(self.sent_to_network[hlc_timestamp_2][0], self.sent_to_network[hlc_timestamp_2][1])

        self.assertEqual(2, len(self.sent_to_network[hlc_timestamp_3]))
        self.assertNotEqual(self.sent_to_network[hlc_timestamp_3][0], self.sent_to_network[hlc_timestamp_3][1])

        # TEST Stu sent Jeff currency three times successfully
        stu_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        stu_balance_delta = stu_balance_before - stu_balance_after
        self.assertEqual(str(tx_amount * 3), str(stu_balance_delta))

        jeff_balance_after = self.tn.get_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        self.assertEqual(str(tx_amount * 3), str(jeff_balance_after))

    '''
        Because of REWARDS nodes will always get different state changes after processing a new earlier TX.
        Commenting this out for now.
    '''
    '''
    def test_reprocessing__should_reprocess__not_send_new_results_if_result_is_the_same(self):

        # This will validate the nodes don't resend results after reprocessing a tx and the result was the same.
        # TX #1 and #3 are related but TX #2 is early and causes reprocessing, but it's state is unrelated to #2 and #3

        self.create_and_start_node()

        # stop the validation queue
        self.await_async_process(self.node.pause_validation_queue)
        # disable the unpausing of the validation queue
        self.tn.node.main_processing_queue.unpause_all_queues = self.mock_unpause_all_queues

        # Mock the node's store_solution_and_send_to_network function, so we can see if it was called
        self.node.actual_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = self.mock_store_solution_and_send_to_network

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        stu_balance_before = self.tn.get_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        tx_amount = 200.1

        # Send from Stu to Jeff
        tx_message_1 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        # Send from Jeff to Oliver
        tx_message_2 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.oliver_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']

        # Send from Stu to Archer
        tx_message_3 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # Process TX#1 and TX#2
        self.node.main_processing_queue.append(tx=tx_message_1)
        self.node.main_processing_queue.append(tx=tx_message_3)

        while self.tn.node.get_last_processed_hlc() != hlc_timestamp_3:
            self.async_sleep(0.1)

        # TEST Stu, Jeff and Archer have expected balances after completed currency transactions
        ## Stu sent 2 currency transactions
        stu_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.stu_wallet.verifying_key}')
        stu_balance_mid_delta = stu_balance_before - stu_balance_mid
        self.assertEqual(str(tx_amount * 2), str(stu_balance_mid_delta))

        ## Jeff received 1 currency TX
        jeff_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.jeff_wallet.verifying_key}')
        self.assertEqual(str(tx_amount), str(jeff_balance_mid))

        ## Archer received 1 currency TX
        archer_balance_mid = self.tn.get_cached_smart_contract_value(key=f'currency.balances:{self.archer_wallet.verifying_key}')
        self.assertEqual(str(tx_amount), str(archer_balance_mid))

        ## TX#1 and TX#3 have sent their results to the network
        self.assertEqual(1, len(self.sent_to_network.get(hlc_timestamp_1)))
        self.assertEqual(1, len(self.sent_to_network.get(hlc_timestamp_3)))

        # Process TX#2 to cause reprocessing
        self.node.main_processing_queue.append(tx=tx_message_2)

        self.async_sleep(0.5)
        while self.tn.node.main_processing_queue.detected_rollback == True:
            self.async_sleep(0.1)

        self.async_sleep(300)

        # TEST that each HCL should have only 1 result in the sent_to_network test object. This shows that only 1
        # result was sent to the network.
        self.assertEqual(1, len(self.sent_to_network.get(hlc_timestamp_1)))
        self.assertEqual(1, len(self.sent_to_network.get(hlc_timestamp_2)))
        self.assertEqual(1, len(self.sent_to_network.get(hlc_timestamp_3)))
    '''
    '''
        Because of REWARDS nodes will always get different state changes after processing a new earlier TX.
        Commenting this out for now.
        IF ever reinstated this test case needs to be fixed as it won't pass anyway.
    '''
    '''
    def test_reprocessing_should_not_send_new_results_if_same_state(self):


        # This will validate the nodes don't resend results after reprocessing a transaction and getting the same state
        # TX #2 and #3 are related and are attempts at sending currency from zero balances (should fail both times)
        # TX #1 is early and will send a balance that TX #2 will send (all of it).
        # TX #3 will reprocess because it read the keys from TX #2's writes and will reprocess the same failed tx (zero
        # balance still.  This will not cause the results to get resent to the network.

        self.create_and_start_node()

        # stop the validation queue
        self.await_async_process(self.node.pause_validation_queue)
        # disable the unpausing of the validation queue
        self.tn.node.main_processing_queue.unpause_all_queues = self.mock_unpause_all_queues

        # Mock the node's store_solution_and_send_to_network function, so we can see if it was called
        self.node.actual_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = self.mock_store_solution_and_send_to_network

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        tx_amount = 200.1
        # Send from Stu to Jeff

        tx_message_1 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        # Send from Jeff to Oliver
        tx_message_2 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_2= tx_message_2['hlc_timestamp']

        # Send from Send from Stu to Archer
        tx_message_3 = self.node.make_tx_message(tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)
        self.async_sleep(0.1)

        # Mock the node's store_solution_and_send_to_network function so we can see if it was called
        self.node.mock_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = mock_store_solution_and_send_to_network

        self.node.main_processing_queue.append(tx=tx_message_1)
        self.async_sleep(0.1)

        self.assertTrue(sent_to_network.get(hlc_timestamp_1, False))
        self.assertTrue(sent_to_network.get(hlc_timestamp_2, False))
        self.assertFalse(sent_to_network.get(hlc_timestamp_3, False))
    '''

    '''
        The nodes no longer process blocks out of order.
        Commenting this out for now
    '''
    '''
    def test_reprocess_after_hard_apply_earilier_block_with_key_keys(self):
        # Test to make sure we reprocess transactions properly when hard applying am earlier block that has new keys
        # To do this we will create a peer node that processes the transactions in order, and then hard apply those
        # processing results out of order to our tester node.  With the state applied we will then process a tx on the
        # node and then send a new consensus block that is earlier than all the current info.  This should cause
        # reprocessing of the tx we processed ourselves

        # Create and start the nodes
        self.create_a_node(node_num=0)

        m_wallet = Wallet()
        constitution = {
                'masternodes': [m_wallet.verifying_key],
                'delegates': []
            }

        bootnodes = {}
        bootnodes[m_wallet.verifying_key] = 'tcp://127.0.0.1:19002'

        node_peer = self.create_a_node(
            node_num=2,
            constitution=constitution,
            bootnodes=bootnodes
        )

        self.start_all_nodes()

        # Stop the node's validation queue to prevent consensus on our results
        self.node.validation_queue.stop()

        # Create a function to intercept the calling of the send to network function so we can see which HLCs this was
        # called for
        sent_to_network = {}
        def mock_store_solution_and_send_to_network(processing_results):
            sent_to_network[processing_results['hlc_timestamp']] = True
            self.node.mock_store_solution_and_send_to_network(processing_results=processing_results)

        recipient_wallet_1 = Wallet()
        recipient_wallet_2 = Wallet()
        tx_amount = 100.5

        # create processing results from another node. These will be added to create state from consensus.
        # tx_1 will give recipient_wallet_1 the balance to send jeff in tx_4 after reprocessing
        tx_message_1 = self.node.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet_1.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1.get('hlc_timestamp')

        processing_results_1 = self.process_a_tx(node=node_peer, tx_message=tx_message_1)
        node_peer.main_processing_queue.append(tx=tx_message_1)

        tx_message_2 = self.node.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet_2.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2.get('hlc_timestamp')
        processing_results_2 = self.process_a_tx(node=node_peer, tx_message=tx_message_2)

        tx_message_3 = self.node.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet_2.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3.get('hlc_timestamp')
        processing_results_3 = self.process_a_tx(node=node_peer, tx_message=tx_message_3)

        # This will fail the first time we run it because we don't know that recipient_wallet_1 has a balance until
        # tx_1 is processed via consensus
        tx_message_4 = self.node.make_tx_message(tx=get_new_currency_tx(
            wallet=recipient_wallet_1,
            to=self.jeff_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_4 = tx_message_4.get('hlc_timestamp')

        # Hard apply these processing results to get some state on our tester node
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_2)
        # Validate state was applied
        recipient_2_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_2.verifying_key}')
        self.assertEqual(str(tx_amount), str(recipient_2_balance))

        self.await_hard_apply_block(node=self.node, processing_results=processing_results_3)
        # Validate state was applied
        recipient_2_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_2.verifying_key}')
        self.assertEqual(str(tx_amount*2), str(recipient_2_balance))

        # Validate both blocks processed
        self.assertIsNotNone(2, self.node.get_current_height())
        self.assertIsNotNone(hlc_timestamp_3, self.node.last_processed_hlc)

        # Process tx4 through the tester node so we get a result
        self.node.main_processing_queue.append(tx=tx_message_4)
        self.async_sleep(0.1)

        # Mock the node's store_solution_and_send_to_network function so we can see if it was called
        self.node.mock_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = mock_store_solution_and_send_to_network

        # Apply the earlier block to our tester node
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_1)

        # Restart Validation Queue to get consensus on the latest message
        self.node.validation_queue.start()
        self.async_sleep(0.1)

        # Validate state balances are as expected after reprocessing
        recipient_1_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_1.verifying_key}')
        recipient_2_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_2.verifying_key}')
        jeff_balance = self.node.driver.get(key=f'currency.balances:{self.jeff_wallet.verifying_key}')

        self.assertEqual('0.0', str(recipient_1_balance))
        self.assertEqual(str(tx_amount * 2), str(recipient_2_balance))
        self.assertEqual(str(tx_amount), str(jeff_balance))

        # Validate out new solution was sent to the rest of the nodes
        self.assertTrue(sent_to_network[hlc_timestamp_4])
    '''

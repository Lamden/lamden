from lamden.nodes.masternode import masternode
from lamden.nodes import base
from lamden import router, storage, network, authentication
from lamden.crypto.wallet import Wallet
from lamden.crypto import canonical
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.db import encoder
from contracting.stdlib.bridge.decimal import ContractingDecimal
import zmq.asyncio
import asyncio
import time
import json

from operator import itemgetter

from unittest import TestCase


def generate_blocks(number_of_blocks):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        new_block = canonical.block_from_subblocks(
            subblocks=[],
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks

def get_new_tx(to=None, amount=200.1, sender=None):
    return {
            'metadata': {
                'signature': '7eac4c17004dced6d079e260952fffa7750126d5d2c646ded886e6b1ab4f6da1e22f422aad2e1954c9529cfa71a043af8c8ef04ccfed6e34ad17c6199c0eba0e',
                'timestamp': 1624049397
            },
            'payload': {
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': amount,
                    'to': to or '6e4f96fa89c508d2842bef3f7919814cd1f64c16954d653fada04e61cc997206'
                },
                'sender': sender or "d48b174f71efb9194e9cd2d58de078882bd172fcc7c8ac5ae537827542ae604e",
                'stamps_supplied': 100,
                'nonce': 0,
                'processor': '92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e'
            }
        }

def get_new_block(
        signer="testuser",
        hash='f' * 64,
        number=1,
        hlc_timestamp='1',
        to=None,
        amount=None,
        sender=None,
        tx=None
):
    blockinfo = {
        "hash": hash,
        "number": number,
        "previous": "0000000000000000000000000000000000000000000000000000000000000000",
        "subblocks": [
          {
            "input_hash": "b48f385f46b2f836e878fdbc3e82d63cc747e92dd3df368b38424cd9aa230de5",
            "merkle_leaves": "3f4a582eb4b32b1a1f6568d70e6414743ea15fa673932d3075bbc3c9f9feed31",
            "signatures": [
              {
                "signature": "dc440f3db9cca56b41619aa9d55ec726ae30eb5e359d8954ee5d2692a54680218c59395547aaf8a556be655f8db99a7ea6d6a086b26d3210dbb0101472a7890b",
                "signer": signer
              }
            ],
            "subblock": 0,
            "transactions": [
              {
                "hash": "467ebaa7304d6bc9871ba0ef530e5e8b6dd7331f6c3ae7a58fa3e482c77275f3",
                "hlc_timestamp": hlc_timestamp,
                "result": "None",
                "stamps_used": 18,
                "state": [
                  {
                    "key": "lets",
                    "value": "go"
                  },
                  {
                    "key": "blue",
                    "value": "jays"
                  }
                ],
                "status": 0,
                "transaction": tx or get_new_tx(to=to, amount=amount, sender=sender)
              }
            ]
          }
        ]
      }

    return blockinfo

class TestNode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.num_of_nodes = 0

        self.blocks = storage.BlockStorage()

        self.driver = ContractDriver(driver=InMemDriver())

        self.stu_wallet = Wallet()

        self.b = masternode.BlockService(
            blocks=self.blocks,
            driver=self.driver
        )

        self.blocks.flush()
        self.driver.flush()

        self.authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

    def tearDown(self):
        self.authenticator.authenticator.stop()
        self.ctx.destroy()
        self.loop.close()
        self.b.blocks.flush()
        self.b.driver.flush()

    def create_a_node(self, constitution=None):
        driver = ContractDriver(driver=InMemDriver())

        dl_wallet = Wallet()
        mn_wallet = Wallet()

        constitution = constitution or {
                'masternodes': [mn_wallet.verifying_key],
                'delegates': [dl_wallet.verifying_key]
            }

        node = base.Node(
            socket_base=f'tcp://127.0.0.1:{self.num_of_nodes}',
            ctx=self.ctx,
            wallet=mn_wallet,
            constitution=constitution,
            driver=driver,
            delay={
                'base': 0.01,
                'self': 0.01
            }
        )

        node.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[self.stu_wallet.verifying_key],
            value=1_000_000
        )

        node.driver.commit()

        self.num_of_nodes = self.num_of_nodes + 1

        return node

    def await_async_process(self, process):
        tasks = asyncio.gather(
            process()
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

    def start_node(self, node):
        # Run process next, no consensus should be met as ideal is still possible
        self.await_async_process(node.start)

    def test_started(self):
        node = self.create_a_node()
        self.start_node(node)

        self.assertTrue(node.running)

    def test_stopped(self):
        node = self.create_a_node()
        self.start_node(node)
        node.stop()

        self.assertFalse(node.running)

    def test_make_tx_message(self):
        node = self.create_a_node()
        self.start_node(node)

        tx_message = node.make_tx_message(tx=get_new_tx())

        tx, timestamp, hlc_timestamp, signature, sender, input_hash = itemgetter(
            'tx', 'timestamp', 'hlc_timestamp', 'signature', 'sender', 'input_hash'
        )(tx_message)

        self.assertIsNotNone(tx)
        self.assertIsNotNone(timestamp)
        self.assertIsNotNone(hlc_timestamp)
        self.assertIsNotNone(signature)
        self.assertIsNotNone(sender)
        self.assertIsNotNone(input_hash)

    def test_check_main_processing_queue(self):
        node = self.create_a_node()
        self.start_node(node)

        # stop the validation queue
        node.validation_queue.stop()

        tx_message = node.make_tx_message(tx=get_new_tx())
        hlc_timestamp = tx_message['hlc_timestamp']

        # add this tx the processing queue so we can process it
        node.main_processing_queue.append(tx=tx_message)

        self.async_sleep(0.05)

        # tx was processed
        self.assertEqual(0, len(node.main_processing_queue))
        print({
            'hlc_timestamp':hlc_timestamp,
            'last_processed_hlc':node.last_processed_hlc
        })
        self.assertEqual(hlc_timestamp, node.last_processed_hlc)

    def test_check_main_processing_queue_not_process_while_stopped(self):
        node = self.create_a_node()
        self.start_node(node)

        # Stop the main processing queue
        node.main_processing_queue.stop()
        self.await_async_process(node.main_processing_queue.stopping)

        tx_message = node.make_tx_message(tx=get_new_tx())
        hlc_timestamp = tx_message['hlc_timestamp']

        # add this tx the processing queue
        node.main_processing_queue.append(tx=tx_message)

        self.async_sleep(0.05)

        # tx was not processed
        self.assertEqual(1, len(node.main_processing_queue))
        self.assertNotEqual(hlc_timestamp, node.last_processed_hlc)

    def test_check_validation_queue(self):
        node = self.create_a_node()
        node.consensus_percent = 0

        self.start_node(node)

        hlc_timestamp = node.hlc_clock.get_new_hlc_timestamp()

        block_info = get_new_block(hlc_timestamp=hlc_timestamp, signer=node.wallet.verifying_key)

        node.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=block_info,
            transaction_processed=get_new_tx()
        )

        #wait for pocessing to complete
        self.await_async_process(lambda: asyncio.sleep(0.05))

        # tx was processed
        self.assertEqual(0, len(node.validation_queue))
        self.assertEqual(hlc_timestamp, node.validation_queue.last_hlc_in_consensus)

    def test_check_validation_queue_not_processed_when_stopped(self):
        node = self.create_a_node()
        node.consensus_percent = 0

        self.start_node(node)

        hlc_timestamp = node.hlc_clock.get_new_hlc_timestamp()

        # stop the validation queue
        node.validation_queue.stop()

        block_info = get_new_block(hlc_timestamp=hlc_timestamp, signer=node.wallet.verifying_key)

        node.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=block_info,
            transaction_processed=get_new_tx()
        )

        #wait for pocessing to complete
        self.async_sleep(0.05)

        # tx was processed
        self.assertEqual(1, len(node.validation_queue))
        self.assertNotEqual(hlc_timestamp, node.validation_queue.last_hlc_in_consensus)

    def test_increments_block_after_consensus(self):
        node = self.create_a_node()
        node.consensus_percent = 0

        self.start_node(node)

        tx_message = node.make_tx_message(tx=get_new_tx())

        node.main_processing_queue.append(tx_message)

        #wait for pocessing to complete
        self.async_sleep(0.05)

        # queue is empty because tx was processed
        self.assertEqual(0, len(node.validation_queue))

        # The main_processing queue can get the current block height from the node
        self.assertEqual(node.main_processing_queue.get_current_height(), node.current_height())

        # Both the queue and the node report the block height is now one, as per the driver
        self.assertEqual(1, node.current_height())
        self.assertEqual(1, node.main_processing_queue.get_current_height())

    def test_update_block_db(self):
        node = self.create_a_node()
        node.consensus_percent = 0

        self.start_node(node)

        block_info = get_new_block()
        node.update_block_db(block_info)

        # queue is empty because tx was processed
        self.assertEqual(0, len(node.validation_queue))

        # The main_processing queue can get the current block height from the node
        self.assertEqual(node.main_processing_queue.get_current_height(), node.current_height())

        # Both the queue and the node report the block height is now one, as per the driver
        self.assertEqual(1, node.current_height())
        self.assertEqual(1, node.main_processing_queue.get_current_height())

    def test_process_result(self):
        node = self.create_a_node()
        self.start_node(node)

        #stop the queues
        node.main_processing_queue.stop()
        node.validation_queue.stop()

        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = ContractingDecimal(100.5)
        tx_message = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp = tx_message['hlc_timestamp']

        node.main_processing_queue.append(tx=tx_message)

        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(0.05)

        # Process the transaction and get the result
        processing_results = self.await_async_process(node.main_processing_queue.process_next)[0]

        node.process_result(processing_results=processing_results)

        # Last processed hlc_timestamp was set
        self.assertEqual(tx_message['hlc_timestamp'], node.last_processed_hlc)
        # result was added into the validation queue for processing
        self.assertEqual(1, len(node.validation_queue))
        # block height was incremented
        self.assertEqual(1, node.current_height())

        # The the recipient balance from the driver
        recipient_balance_after = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        #recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # The tx that was processed was the one we expected
        self.assertEqual(hlc_timestamp, processing_results['hlc_timestamp'])
        # The recipient's balance was updated
        self.assertEqual(tx_amount, recipient_balance_after)
        self.assertEqual(1, node.current_height())

    def test_process_result_validate_block_info_return_value(self):
        node = self.create_a_node()
        self.start_node(node)

        #stop the queues
        node.main_processing_queue.stop()
        node.validation_queue.stop()

        # create a transaction
        tx_message = node.make_tx_message(tx=get_new_tx())
        hlc_timestamp = tx_message['hlc_timestamp']

        node.main_processing_queue.append(tx=tx_message)

        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(0.05)

        # Process the transaction and get the result
        processing_results = self.await_async_process(node.main_processing_queue.process_next)[0]

        block_info = node.process_result(processing_results=processing_results)
        print(block_info)
        hash, number, previous, subblocks = itemgetter(
            'hash', 'number', 'previous', 'subblocks'
        )(block_info)

        self.assertIsNotNone(hash)
        self.assertIsNotNone(number)
        self.assertIsNotNone(previous)
        self.assertIsNotNone(subblocks)

    def test_soft_apply_current_state(self):
        node = self.create_a_node()
        self.start_node(node)

        #stop the queues
        node.main_processing_queue.stop()
        node.validation_queue.stop()

        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = 200.5
        tx_message = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp = tx_message['hlc_timestamp']

        # Add the tx to the stopped processing queue
        node.main_processing_queue.append(tx=tx_message)

        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(0.05)

        # Process the transaction and get the result
        processing_results = self.await_async_process(node.main_processing_queue.process_next)[0]
        # Run the Soft Apply logic
        node.soft_apply_current_state(processing_results['hlc_timestamp'])

        # Get the recipient balance from the driver
        recipient_balance_after = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        #recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # The tx that was processed was the one we expected
        self.assertEqual(hlc_timestamp, processing_results['hlc_timestamp'])
        # The recipient's balance was updated
        self.assertEqual(tx_amount, recipient_balance_after)

        # TODO Test cases for rewarded wallet prior state changes

    def test_state_values_after_multiple_transactions(self):
        node = self.create_a_node()
        self.start_node(node)

        print("sending first transaction")
        # ___ SEND 1 Transaction ___
        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = 100.5
        tx_message = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp_1 = tx_message['hlc_timestamp']
        # add to processing queue
        node.main_processing_queue.append(tx=tx_message)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(node.main_processing_queue))

        # Get the recipient balance from the driver
        recipient_balance_after = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # The recipient's balance was updated
        self.assertEqual("100.5", recipient_balance_after)
        # The block was incremented
        self.assertEqual(1, node.current_height())
        self.assertEqual(0, len(node.main_processing_queue))

        print("sending second transaction")
        # ___ SEND ANOTHER Transaction ___
        # create a transaction
        tx_message = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))

        # add to processing queue
        node.main_processing_queue.append(tx=tx_message)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(node.main_processing_queue))

        # Get the recipient balance from the driver
        recipient_balance_after = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # The recipient's balance was updated
        self.assertEqual("201.0", recipient_balance_after)
        # The block was incremented
        self.assertEqual(2, node.current_height())

    def test_rollback_drivers(self):
        node = self.create_a_node()
        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        node.consensus_percent = 0

        self.start_node(node)

        # ___ SEND 1 Transaction ___
        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = 100.5
        tx_message = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp_1 = tx_message['hlc_timestamp']
        # add to processing queue
        node.main_processing_queue.append(tx=tx_message)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(node.main_processing_queue))

        # ___ SEND ANOTHER Transaction ___
        # create a transaction
        tx_message = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp_2 = tx_message['hlc_timestamp']

        # Stop the validation queue so this this transaction doesn't have consensus performed. The assumption is that we
        # are not in consensus and need to rollback to previous transaction.
        node.validation_queue.stop()

        # add to processing queue
        node.main_processing_queue.append(tx=tx_message)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(node.main_processing_queue))

        # Get the recipient balance from the driver
        recipient_balance_after = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # --- TESTS TO MAKE SURE THE SETUP BEFORE ROLLBACK IS LEGIT ---
        # The recipient's balance was updated
        self.assertEqual("201.0", recipient_balance_after)
        print({"recipient_balance_after": recipient_balance_after})
        # The block was incremented
        self.assertEqual(2, node.current_height())
        self.assertEqual(hlc_timestamp_2, node.last_processed_hlc)
        # ---

        # Initiate rollback to block 1 (hlc_timestamp_1) test state values
        # to prevent auto processing and allow us to test the state of them after the rollback
        node.main_processing_queue.stop()

        node.rollback_drivers()

        # --- TEST STATE AFTER ROLLBACK DRIVERS ---

        # Get the recipient balance from the driver
        recipient_balance_after_rollback = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after_rollback = json.loads(encoder.encode(recipient_balance_after_rollback))['__fixed__']

        print({"recipient_balance_after_rollback": recipient_balance_after_rollback})
        print({"node_current_height": node.current_height()})

        # The recipient's balance was updated
        self.assertEqual("100.5", recipient_balance_after_rollback)
        # The block was incremented
        self.assertEqual(1, node.current_height())

    def test_add_processed_transactions_back_into_main_queue(self):
        # After a rollback we need to reprocess all the transactions with a higher hlc_timestamp than the rollback point
        # To do this test we need to simply add some transactions into the validation_queue.validation_results storage
        # state and then call the function.  The transaction info from those results should be added back into the main
        # queue

        # The content of the block results does not matter here as we are testing the adding from one queue to another
        # and not the processing of the results

        node = self.create_a_node()
        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        node.consensus_percent = 0

        self.start_node(node)
        # Stop both queues to allow us to call the methods manually for this test as well as the ability to test the
        # state afterwards.
        node.main_processing_queue.stop()
        node.validation_queue.stop()

        # add two block results to the validation queue
        # __ TX 1 __
        tx_message_1 = node.make_tx_message(tx=get_new_tx(
            to="stu",
            amount=1,
            sender=node.wallet.verifying_key
        ))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']
        node.validation_queue.append(
            hlc_timestamp=hlc_timestamp_1,
            block_info=get_new_block(signer=node.wallet.verifying_key, hash="1", tx=tx_message_1),
            transaction_processed=tx_message_1
        )

        # __ TX 2 __
        tx_message_2 = node.make_tx_message(tx=get_new_tx(
            to="jeff",
            amount=2,
            sender=node.wallet.verifying_key
        ))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']
        node.validation_queue.append(
            hlc_timestamp=hlc_timestamp_2,
            block_info=get_new_block(signer=node.wallet.verifying_key, hash="2", tx=tx_message_2),
            transaction_processed=tx_message_2
        )
        node.add_processed_transactions_back_into_main_queue()

        # --- TEST STATE AFTER ROLLBACK DRIVERS ---
        # The main processing queue now has 2transaction in it
        self.assertEqual(2, len(node.main_processing_queue))

        # The transactions are the same two added above
        # sort the queue so we can know the order of our transactions in the queue
        node.main_processing_queue.sort_queue()

        # Transaction 1 exists in main processing queue index 0
        self.assertEqual(hlc_timestamp_1, node.main_processing_queue[0]['hlc_timestamp'])

        # Transaction 2 exists in main processing queue index 1
        self.assertEqual(hlc_timestamp_2, node.main_processing_queue[1]['hlc_timestamp'])

    def test_rollback(self):
        # This will test the main rollback function of the node
        # Test setup involves 3 transactions
        # First sent 1 transactions and hard apply its result (so it "has consensus")
        # Next send 2 more transactions, and process the first and then rolling back afterwards (the thrid will not be
        # processed before the rollback
        # After rollback is called the node should automatically add the second transaction back in and then process
        # the second and thrid transactions
        # Test the state afterwards to validate the test case.

        node = self.create_a_node()
        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        node.consensus_percent = 0

        self.start_node(node)

        # ___ Transaction ONE ___
        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = 100.5
        tx_message_1 = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']
        # add to main processing queue
        node.main_processing_queue.append(tx=tx_message_1)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        # tx was processes by the main queue
        self.assertEqual(0, len(node.main_processing_queue))
        # result was in consensus and hard applied (this sets our rollback point)
        self.assertEqual(hlc_timestamp_1, node.validation_queue.last_hlc_in_consensus)

        # Stop the queues so we can manually run the methods for this test
        node.validation_queue.stop()
        node.main_processing_queue.stop()
        self.await_async_process(node.main_processing_queue.stopping)

        # Send transactions TWO and THREE to the main processing queue

        # ___ Transaction TWO  ___
        # create a transaction
        tx_message_2 = node.make_tx_message(tx=get_new_tx(
            to=recipient_wallet.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']
        # add to main processing queue
        node.main_processing_queue.append(tx=tx_message_2)

        # ___ Transaction THREE  ___
        jeff_wallet = Wallet()
        # create a transaction
        tx_message_3 = node.make_tx_message(tx=get_new_tx(
            to=jeff_wallet.verifying_key,
            amount=700.5,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']
        # add to main processing queue
        node.main_processing_queue.append(tx=tx_message_3)

        # validate both transactions are in the main processing queue
        self.assertEqual(2, len(node.main_processing_queue))

        # Manually processes the second transaction, do not hard apply.
        self.async_sleep(1)
        self.await_async_process(node.process_main_queue)

        # ___ Validate test setup state before rollback ___
        # validate the transaction was processed from the main queue
        self.assertEqual(hlc_timestamp_2, node.last_processed_hlc)

        # validate the third transaction remains in the queue
        self.assertEqual(1, len(node.main_processing_queue))

        # validate the first transaction is still the rollback point
        self.assertEqual(hlc_timestamp_1, node.validation_queue.last_hlc_in_consensus)
        # ---

        # ROLLBACK
        # This will rollback state to just after the first transaction was processed
        # Readd the second transction back into the main processing queue
        # Restart both the main processsing and validation queues
        # automatically re-process the second transaction and then process the third, hard applying the state on both

        self.await_async_process(node.rollback)
        self.async_sleep(2)

        # ___ Validate test results ___
        # All transactions were processed from the main queue
        self.assertEqual(0, len(node.main_processing_queue))
        # The third transaction was not only the last one processes but the last one in consensus
        self.assertEqual(hlc_timestamp_3, node.last_processed_hlc)
        self.assertEqual(hlc_timestamp_3, node.validation_queue.last_hlc_in_consensus)
        # Validate both the recipent_wallet and jeff_wallet have the correct balances
        recipient_balance = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        self.assertEqual("201.0", json.loads(encoder.encode(recipient_balance))['__fixed__'])
        jeff_balance = node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[jeff_wallet.verifying_key],
            mark=False
        )
        self.assertEqual("700.5", json.loads(encoder.encode(jeff_balance))['__fixed__'])
        # Validate the block height
        self.assertEqual(3, node.current_height())
        # Validate the queues are running
        self.assertTrue(node.main_processing_queue.running)
        self.assertTrue(node.validation_queue.running)


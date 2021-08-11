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

DEFAULT_BLOCK = '0000000000000000000000000000000000000000000000000000000000000000'

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
        hash=64 * f'1',
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
            testing=True,
            metering=False,
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

    def get_amount_from_driver(self, driver, item):
        return self.decode_to_string(driver.get(item))

    def get_amount_from_db(self, driver, item):
        return self.decode_to_string(driver.driver.get(item))

    def decode_to_string(self, value):
        decoded = json.loads(encoder.encode(value))
        if decoded is None:
            return None
        return decoded.get('__fixed__') or decoded

    def start_node(self, node):
        # Run process next, no consensus should be met as ideal is still possible
        self.await_async_process(node.start)

    def test_consensus_with_me(self):
        # Create a node and start it
        node = self.create_a_node()
        node.consensus_percent = 51
        node.validation_queue.get_peers_for_consensus = lambda: ['1', '2']
        self.start_node(node)

        # create a transaction and send it to create a pending delta
        receiver_wallet_1 = Wallet()
        tx_amount = 100.5
        tx_message_1 = node.make_tx_message(tx=get_new_tx(
            to=receiver_wallet_1.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        node.main_processing_queue.append(tx_message_1)
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        # wait for node to process and store results
        self.async_sleep(0.1)

        block_info = node.validation_queue.validation_results[hlc_timestamp_1]['solutions'][node.wallet.verifying_key]
        node.validation_queue.append(
            block_info=block_info,
            hlc_timestamp=hlc_timestamp_1,
            node_vk=Wallet().verifying_key,
            transaction_processed=tx_message_1
        )
        self.assertEqual(1, len(node.validation_queue))
        self.async_sleep(0.1)

        # Amount set in cache
        driver_amount = self.get_amount_from_driver(node.driver, f"currency.balances:{receiver_wallet_1.verifying_key}")
        self.assertEqual(str(tx_amount), driver_amount)

        # Amount saved to database
        db_amount = self.get_amount_from_db(node.driver, f"currency.balances:{receiver_wallet_1.verifying_key}")
        self.assertEqual(str(tx_amount), db_amount)

        # Block height is correct
        self.assertEqual(block_info['number'], node.get_current_height())
        self.assertEqual(block_info['number'], node.get_consensus_height())

        # Block Hash is correct
        self.assertEqual(block_info['hash'], node.get_current_hash())
        self.assertEqual(block_info['hash'], node.get_consensus_hash())

    def test_consensus_WITHOUT_me(self):
        # Create a node and start it
        node = self.create_a_node()
        node.consensus_percent = 51
        node.validation_queue.get_peers_for_consensus = lambda: ['1', '2']
        self.start_node(node)

        # create a transaction and send it to create a pending delta
        receiver_wallet_1 = Wallet()
        tx_amount = 100.5
        tx_message_1 = node.make_tx_message(tx=get_new_tx(
            to=receiver_wallet_1.verifying_key,
            amount=tx_amount,
            sender=self.stu_wallet.verifying_key
        ))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        # add two solutions from other nodes
        block_info = get_new_block(tx=tx_message_1, hlc_timestamp=hlc_timestamp_1)

        node.validation_queue.append(
            block_info=block_info,
            hlc_timestamp=hlc_timestamp_1,
            node_vk=Wallet().verifying_key,
            transaction_processed=tx_message_1
        )
        node.validation_queue.append(
            block_info=block_info,
            hlc_timestamp=hlc_timestamp_1,
            node_vk=Wallet().verifying_key,
            transaction_processed=tx_message_1
        )
        self.assertEqual(2, len(node.validation_queue))
        self.async_sleep(0.1)

        # Amount set in cache
        driver_amount = self.get_amount_from_driver(node.driver, f"currency.balances:{receiver_wallet_1.verifying_key}")
        self.assertEqual(str(tx_amount), driver_amount)

        # Amount saved to database
        db_amount = self.get_amount_from_db(node.driver, f"currency.balances:{receiver_wallet_1.verifying_key}")
        self.assertEqual(str(tx_amount), db_amount)

        # Block height is correct
        self.assertEqual(block_info['number'], node.get_current_height())
        self.assertEqual(block_info['number'], node.get_consensus_height())

        # Block Hash is correct
        self.assertEqual(block_info['hash'], node.get_current_hash())
        self.assertEqual(block_info['hash'], node.get_consensus_hash())
from lamden.nodes.masternode import masternode
from lamden.nodes import base
from lamden import storage
from lamden.crypto.wallet import Wallet

from contracting.db.driver import InMemDriver, ContractDriver

import zmq.asyncio
import asyncio

from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results
from tests.integration.mock.create_directories import remove_fixture_directories

from unittest import TestCase
from pathlib import Path

class TestNode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.num_of_nodes = 0

        self.driver = ContractDriver(driver=InMemDriver())

        self.stu_wallet = Wallet()
        self.jeff_wallet = Wallet()
        self.archer_wallet = Wallet()
        self.oliver_wallet = Wallet()

        self.current_path = Path.cwd()
        self.fixtures_path = f'{self.current_path}/fixtures'
        self.block_storage_path = f'{self.fixtures_path}/block_storage'

        remove_fixture_directories(
            root=self.fixtures_path,
            dir_list=['block_storage'],

        )

        self.nodes = []


        print("\n")

    def tearDown(self):
        for node in self.nodes:
            self.await_async_process(node.stop)
            remove_fixture_directories(
                root=self.block_storage_path,
                dir_list=[node.wallet.verifying_key],

            )

        self.ctx.destroy()
        self.loop.close()

    def create_a_node(self, constitution=None, node_num=0):
        driver = ContractDriver(driver=InMemDriver())

        mn_wallet = Wallet()

        constitution = constitution or {
                'masternodes': [mn_wallet.verifying_key],
                'delegates': []
            }

        bootnodes = {}
        bootnodes[mn_wallet.verifying_key] = f'tcp://127.0.0.1:{19000 + node_num}'

        node = base.Node(
            socket_base=f'tcp://127.0.0.1:{19000 + node_num}',
            ctx=self.ctx,
            wallet=mn_wallet,
            constitution=constitution,
            driver=driver,
            testing=True,
            metering=False,
            delay={
                'base': 0,
                'self': 0
            },
            blocks=storage.BlockStorage(root=f'{self.block_storage_path}/{mn_wallet.verifying_key}')
        )

        node.network.socket_ports['router'] = 19000 + node_num
        node.network.socket_ports['webserver'] = 18080 + node_num
        node.network.socket_ports['publisher'] = 19080 + node_num

        node.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[self.stu_wallet.verifying_key],
            value=1_000_000
        )

        node.driver.commit()

        self.num_of_nodes = self.num_of_nodes + 1

        self.nodes.append(node)

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

    def add_solution(self, node, tx=None, tx_message=None, wallet=None, amount=None, to=None, receiver_wallet=None,
                     node_wallet=None, masternode=None, processing_results=None):
        masternode = masternode or Wallet()
        receiver_wallet = receiver_wallet or Wallet()
        node_wallet = node_wallet or Wallet()

        wallet = wallet or Wallet()
        amount = amount or "10.5"
        to = to or receiver_wallet.verifying_key

        if tx_message is None:
            transaction = tx or get_new_currency_tx(wallet=wallet, amount=amount, to=to)

        tx_message = tx_message or get_tx_message(tx=transaction, node_wallet=masternode)

        processing_results = processing_results or get_processing_results(tx_message=tx_message, node_wallet=node_wallet)

        node.validation_queue.append(processing_results=processing_results)

        return processing_results

    def get_validation_result(self, hlc_timestamp, node, node_vk=None):
        node_vk = node_vk or node.wallet.verifying_key
        for result in node.validation_queue.validation_results_history:
            if hlc_timestamp in result.keys():
                solution = result[hlc_timestamp][1]['solutions'].get(node_vk)
                return result[hlc_timestamp][1]['result_lookup'].get(solution, None)
        return None

    def test_hard_apply_block(self):
        # Hard Apply will mint a new block, apply state and increment block height
        node = self.create_a_node()
        self.start_node(node)

        stu_balance_before = node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        tx_args = {
            'to': self.jeff_wallet.verifying_key,
            'wallet': self.stu_wallet,
            'amount': tx_amount
        }

        tx_message_1 = node.make_tx_message(tx=get_new_currency_tx(**tx_args))

        node.main_processing_queue.append(tx=tx_message_1)

        self.async_sleep(0.1)

        block = node.blocks.get_block(v=1)

        self.assertIsNotNone(block)

        self.assertEqual(tx_amount, node.driver.driver.get(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(stu_balance_before - tx_amount, node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(1, node.current_block_height)

    def test_hard_apply_block_multiple_concurrent(self):
        # Hard Apply will mint new blocks, apply state and increment block height after multiple transactions
        node = self.create_a_node()
        self.start_node(node)

        stu_balance_before = node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_message_1 = node.make_tx_message(tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))

        # Send from Jeff to Archer
        tx_message_2 = node.make_tx_message(tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))

        # Send from Archer to Oliver
        tx_message_3 = node.make_tx_message(tx=get_new_currency_tx(
            to=self.oliver_wallet.verifying_key,
            wallet=self.archer_wallet,
            amount=tx_amount
        ))

        node.main_processing_queue.append(tx=tx_message_1)
        node.main_processing_queue.append(tx=tx_message_2)
        node.main_processing_queue.append(tx=tx_message_3)

        self.async_sleep(0.2)

        self.assertIsNotNone(node.blocks.get_block(v=1))
        self.assertIsNotNone(node.blocks.get_block(v=2))
        self.assertIsNotNone(node.blocks.get_block(v=3))

        self.assertEqual(stu_balance_before - tx_amount, node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(0, node.driver.driver.get(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(0, node.driver.driver.get(f'currency.balances:{self.archer_wallet.verifying_key}'))
        self.assertEqual(tx_amount, node.driver.driver.get(f'currency.balances:{self.oliver_wallet.verifying_key}'))
        self.assertEqual(3, node.current_block_height)


    def test_hard_apply_block_multiple_nonconcurrent(self):
        # Hard Apply will mint new blocks, apply state and increment block height after multiple transactions that come
        # in out of order
        # have a node process the results correctly and then add them to another node out of order

        def get_peers_for_consensus():
            return {"peer_1": "peer_1", "peer_2": "peer_2"}

        # This node we will use for the testing
        node_1 = self.create_a_node(node_num=0)
        self.start_node(node_1)

        # This node we will use to create the processing results which will be passed to node_1
        node_2 = self.create_a_node(node_num=1)
        node_2.validation_queue.get_peers_for_consensus = get_peers_for_consensus
        self.start_node(node_2)

        stu_balance_before = node_2.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')

        # Create three transactions
        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_message_1 = node_2.make_tx_message(tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1.get('hlc_timestamp')

        # Send from Jeff to Archer
        tx_message_2 = node_2.make_tx_message(tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2.get('hlc_timestamp')

        # Send from Archer to Oliver
        tx_message_3 = node_2.make_tx_message(tx=get_new_currency_tx(
            to=self.oliver_wallet.verifying_key,
            wallet=self.archer_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3.get('hlc_timestamp')

        ## Have node_1 process the transactions in order to generate the results

        node_2.main_processing_queue.append(tx=tx_message_1)
        node_2.main_processing_queue.append(tx=tx_message_2)
        node_2.main_processing_queue.append(tx=tx_message_3)

        # Await processing and consensus
        self.async_sleep(0.2)

        processing_results_1 = self.get_validation_result(hlc_timestamp=hlc_timestamp_1, node=node_2)
        processing_results_2 = self.get_validation_result(hlc_timestamp=hlc_timestamp_2, node=node_2)
        processing_results_3 = self.get_validation_result(hlc_timestamp=hlc_timestamp_3, node=node_2)

        # Add results from TX2 and TX3
        self.add_solution(node=node_1, processing_results=processing_results_2)
        self.add_solution(node=node_1, processing_results=processing_results_3)

        # Await processing and consensus
        self.async_sleep(0.2)

        # Validate blocks are created
        self.assertIsNotNone(node_1.blocks.get_block(v=1))
        self.assertIsNotNone(node_1.blocks.get_block(v=2))

        # Add results from TX1
        self.add_solution(node=node_1, processing_results=processing_results_1)

        # Await processing and consensus
        self.async_sleep(0.1)

        # Validate the blocks are in hlc_timestamps order
        block_1 = node_1.blocks.get_block(v=1)
        block_2 = node_1.blocks.get_block(v=2)
        block_3 = node_1.blocks.get_block(v=3)
        self.assertEqual(hlc_timestamp_1, block_1.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_2, block_2.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_3, block_3.get('hlc_timestamp'))

        self.assertEqual(stu_balance_before - tx_amount, node_1.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(0, node_1.driver.get(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(0, node_1.driver.get(f'currency.balances:{self.archer_wallet.verifying_key}'))
        self.assertEqual(tx_amount, node_1.driver.get(f'currency.balances:{self.oliver_wallet.verifying_key}'))
        self.assertEqual(3, node_1.current_block_height)

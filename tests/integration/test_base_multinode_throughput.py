from tests.integration.mock import mocks_new
from lamden.nodes.filequeue import FileQueue

from lamden import router, storage, network, authentication
from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction


from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.db import encoder

import zmq.asyncio
import asyncio
import httpx
import random
import json
import time
import pprint

from unittest import TestCase


class TestMultiNode(TestCase):
    def setUp(self):
        self.masternodes = [Wallet(), Wallet(), Wallet()]
        self.delegates = [Wallet(), Wallet(), Wallet()]

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.driver = ContractDriver(driver=InMemDriver())
        self.client = ContractingClient(driver=self.driver)
        self.client.flush()

        self.queue = FileQueue(root='./fixtures/.lamden/txq')

    def tearDown(self):
        self.client.flush()
        self.driver.flush()
        self.ctx.destroy()
        self.loop.close()

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

    async def send_transaction(self, tx):
        self.queue.append(tx)

    def test_mock_network_init_makes_correct_number_of_nodes(self):
        n = mocks_new.MockNetwork(num_of_delegates=1, num_of_masternodes=1, ctx=self.ctx, metering=False)
        self.assertEqual(len(n.masternodes), 1)
        self.assertEqual(len(n.delegates), 1)

    def test_mock_network_init_makes_correct_number_of_nodes_many_nodes(self):
        n = mocks_new.MockNetwork(num_of_delegates=123, num_of_masternodes=143, ctx=self.ctx, metering=False)
        self.assertEqual(len(n.masternodes), 143)
        self.assertEqual(len(n.delegates), 123)

    def test_mock_network_init_creates_correct_bootnodes(self):
        # 2 mn, 3 delegate
        expected_ips = [
            'tcp://127.0.0.1:18000',
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002',
            'tcp://127.0.0.1:18003',
            'tcp://127.0.0.1:18004',
            'tcp://127.0.0.1:18005',
            'tcp://127.0.0.1:18006',
            'tcp://127.0.0.1:18007',
            'tcp://127.0.0.1:18008'
        ]

        n = mocks_new.MockNetwork(num_of_masternodes=3, num_of_delegates=6, ctx=self.ctx)

        self.assertEqual(n.masternodes[0].tcp, expected_ips[0])
        self.assertEqual(n.masternodes[1].tcp, expected_ips[1])
        self.assertEqual(n.masternodes[2].tcp, expected_ips[2])
        self.assertEqual(n.delegates[0].tcp, expected_ips[3])
        self.assertEqual(n.delegates[1].tcp, expected_ips[4])
        self.assertEqual(n.delegates[2].tcp, expected_ips[5])
        self.assertEqual(n.delegates[3].tcp, expected_ips[6])
        self.assertEqual(n.delegates[4].tcp, expected_ips[7])
        self.assertEqual(n.delegates[5].tcp, expected_ips[8])

    def test_startup_with_manual_node_creation_and_single_block_works(self):
        m = mocks_new.MockMaster(ctx=self.ctx, index=1)
        d = mocks_new.MockDelegate(ctx=self.ctx, index=2)

        bootnodes = {
            m.wallet.verifying_key: m.tcp,
            d.wallet.verifying_key: d.tcp
        }

        constitution = {
            'masternodes': [m.wallet.verifying_key],
            'delegates': [d.wallet.verifying_key]
        }

        m.set_start_variables(bootnodes, constitution)
        d.set_start_variables(bootnodes, constitution)

        self.await_async_process(m.start)
        self.await_async_process(d.start)

        self.assertTrue(m.obj.running)
        self.assertTrue(d.obj.running)

        sender = Wallet()
        tx_amount = 1_000_000
        tx_1 = transaction.build_transaction(
            wallet=mocks_new.TEST_FOUNDATION_WALLET,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': tx_amount,
                'to': sender.verifying_key
            },
            stamps=10000,
            nonce=0,
            processor=m.wallet.verifying_key
        )

        self.send_transaction(url=m.http, tx=tx_1)
        self.async_sleep(2)

        # dbal = dld.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal = m.driver.get_var(contract='currency', variable='balances', arguments=[sender.verifying_key])
        print({'mbal': mbal, 'tx_amount': tx_amount})
        self.assertEqual(mbal, tx_amount)
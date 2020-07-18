from lamden.crypto import transaction
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, InMemDriver
from contracting.client import ContractingClient
import zmq.asyncio
import asyncio
from copy import deepcopy
from unittest import TestCase
import httpx

from tests.integration.mock import mocks


class TestPump(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        self.driver = ContractDriver(driver=InMemDriver())
        self.client = ContractingClient(driver=self.driver)
        self.client.flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.client.flush()
        self.driver.flush()
        self.ctx.destroy()
        self.loop.close()

    def test_add_new_masternode_with_transactions(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=4, ctx=self.ctx)

        stu = Wallet()
        candidate = Wallet()

        print(candidate.verifying_key)

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': stu.verifying_key
                }
            )

            await asyncio.sleep(2)

            for i in range(30):
                await network.push_tx(
                    wallet=stu,
                    node=network.masternodes[0],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1,
                        'to': 'test'
                    },
                    nonce=i,
                    stamps=1_000_000
                )

            await asyncio.sleep(5)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1,
                    'to': 'test'
                },
                stamps=1_000_000
            )

        self.loop.run_until_complete(test())

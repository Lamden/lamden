import unittest
import zmq.asyncio
from cilantro_ee.contracts import sync
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.storage.vkbook import VKBook
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient


class TestUpgradeMsgs(unittest.TestCase):


    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        ContractingClient().flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()


    def test_init_state(self):
        driver = ContractDriver()
        driver.flush()

        sync.sync_genesis_contracts()

        upg = driver.get_contract_keys('upgrade')
        self.assertIsNotNone(upg)
        print('done')

    # check for upgrade lock
    def test_upg_trigger_1_1(self):
        mns, dls = make_network(1, 1, self.ctx)
        start_up = make_start_awaitable(mns, dls)

        candidate = Wallet()
        stu = Wallet()

        tx1 = make_tx_packed(
            processor = mns[1].wallet.verifying_key(),
            contract_name='upgrade',
            function_name = 'init_upgrade',
            kwargs = {
                'pepper': 'peppertest',
                'initiator_vk': stu,
            },
            sender = candidate,
            drivers = [node.driver for node in mns + dls],
            nonce = 0,
            stamps = 1_000_000,
        )

        async def test():
            await start_up
            await asyncio.sleep(3)
            await send_tx_batch(mns[1], [tx1])
            await asyncio.sleep(5)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        for node in mns + dls:
            v = node.driver.get_var(
                contract='upgrade',
                variable='upg_lock',
                arguments=[])
            self.assertEqual(v, True)



    # test for multiple upgrade triggers
    # test for vote register
    # test for consensys
    # test contract reset
    # test timeout and voter state


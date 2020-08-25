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


class TestFullFlowWithMocks(TestCase):
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

    def test_process_two_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        stu2 = Wallet()
        candidate = Wallet()
        candidate2 = Wallet()

        N_tx= 2
        w_stu =[]
        for k in range(N_tx):
            w_stu.append(Wallet())

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': w_stu[0].verifying_key
                }
            )
            # for k in range(1,N_tx):
            #     await network.make_and_push_tx(
            #         wallet=mocks.TEST_FOUNDATION_WALLET,
            #         contract='currency',
            #         function='transfer',
            #         kwargs={
            #             'amount': 2,
            #             'to': w_stu[0].verifying_key
            #         }
            #     )


            for k1 in range(N_tx -1):
                # await asyncio.sleep(1)
                k = N_tx - k1 - 2
                await network.make_and_push_tx(
                    wallet=w_stu[k],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 10,
                        'to': w_stu[k+1].verifying_key
                    },
                )
            await asyncio.sleep(2)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[w_stu[N_tx-1].verifying_key]
            ), 10)

        self.loop.run_until_complete(test())
        if hasattr(network.delegates[0].obj.transaction_executor,"stop_pool"):
            network.delegates[0].obj.transaction_executor.stop_pool()


    def test_process_single_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        stu2 = Wallet()
        candidate = Wallet()
        candidate2 = Wallet()

        async def test():
            await network.start()
            network.refresh()

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': stu.verifying_key
                }
            )

            await asyncio.sleep(4)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': candidate.verifying_key
                },
            )
            await asyncio.sleep(14)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[candidate.verifying_key]
            ), 1338)

        self.loop.run_until_complete(test())
        if hasattr(network.delegates[0].obj.transaction_executor,"stop_pool"):
            network.delegates[0].obj.transaction_executor.stop_pool()

    def test1_process_batch_2tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        w_stu =[Wallet()]
        w_cand = [Wallet()]

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': w_stu[0].verifying_key
                }
            )
            await asyncio.sleep(2)

            await network.make_and_push_tx(
                wallet=w_stu[0],
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': w_cand[0].verifying_key
                },
            )
            await asyncio.sleep(14)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[w_cand[0].verifying_key]
            ), 1338)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [w_stu[0].verifying_key]
            ), 1_000_000 - 1338 - 0.3)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567 - (1_000_000 + 0.294))

        self.loop.run_until_complete(test())
        if hasattr(network.delegates[0].obj.transaction_executor,"stop_pool"):
            network.delegates[0].obj.transaction_executor.stop_pool()


    def test2_failed_tx(self):
        # 2) A single tx batch with a failed transaction works as expected
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        N_tx= 2
        w_stu =[]
        w_cand = []
        for k in range(N_tx):
            w_stu.append(Wallet())
            w_cand.append(Wallet())

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=mocks.TEST_FOUNDATION_WALLET,
                    contract='currency',
                    function='transfer2',
                    kwargs={
                        'amount': 1_000_000,
                        'to': w_stu[k].verifying_key
                    }
                )
                await asyncio.sleep(2)

        self.loop.run_until_complete(test())
        if hasattr(network.delegates[0].obj.transaction_executor,"stop_pool"):
            network.delegates[0].obj.transaction_executor.stop_pool()

    def test3_process_2tx_non_conflict(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=1, ctx=self.ctx)
        N_tx = 2
        w_stu =[Wallet(), Wallet()]
        w_cand = [Wallet(), Wallet()]

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)

            for i_tx in range(N_tx):
                await network.make_and_push_tx(
                    wallet=mocks.TEST_FOUNDATION_WALLET,
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1_000_000,
                        'to': w_stu[i_tx].verifying_key
                    }
                )
                await asyncio.sleep(2)

                await network.make_and_push_tx(
                    wallet=w_stu[i_tx],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1338,
                        'to': w_cand[i_tx].verifying_key
                    },
                )
                await asyncio.sleep(4)

                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments=[w_cand[i_tx].verifying_key]
                ), 1338)

                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments= [w_stu[i_tx].verifying_key]
                ), 1_000_000 - 1338 - 0.3)

            # self.assertEqual(network.get_var(
            #     contract='currency',
            #     variable='balances',
            #     arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            # ), 288_090_567 - (1_000_000 + 0.297) * N_tx)

        self.loop.run_until_complete(test())
        if hasattr(network.delegates[0].obj.transaction_executor,"stop_pool"):
            network.delegates[0].obj.transaction_executor.stop_pool()


    def test4_process_2tx_rerun(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)
        N_tx = 4
        w_stu =[Wallet()]
        w_cand = [Wallet()]

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)
            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': w_stu[0].verifying_key
                }
            )
            await asyncio.sleep(2)

            for i_tx in range(N_tx):
                await network.make_and_push_tx(
                    wallet=w_stu[0],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1338,
                        'to': w_cand[0].verifying_key
                    },
                )
                await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[w_cand[0].verifying_key]
            ), 1338*N_tx)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [w_stu[0].verifying_key]
            ), 1_000_000 - (1338 + 0.3) * N_tx)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567 - 1_000_000 - 0.28500003 )

        self.loop.run_until_complete(test())
        if hasattr(network.delegates[0].obj.transaction_executor,"stop_pool"):
            network.delegates[0].obj.transaction_executor.stop_pool()


    def test5_process_4_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        N_tx= 2
        w_stu =[]
        w_cand = []
        for k in range(N_tx):
            w_stu.append(Wallet())
            w_cand.append(Wallet())

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=mocks.TEST_FOUNDATION_WALLET,
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1_000_000,
                        'to': w_stu[k].verifying_key
                    }
                )
                await asyncio.sleep(2)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=w_stu[k],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1338,
                        'to': w_cand[k].verifying_key
                    },
                )
                # await asyncio.sleep(4)

            await asyncio.sleep(4)

            for k in range(N_tx):
                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments=[w_cand[k].verifying_key]
                ), 1338)

            for k in range(N_tx):
                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments= [w_stu[k].verifying_key]
                ), 1_000_000 - 1338 - 0.3)

            # self.assertEqual(network.get_var(
            #     contract='currency',
            #     variable='balances',
            #     arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            # ), 288_090_567 - (1_000_000 + 0.294)* N_tx)

        self.loop.run_until_complete(test())
        network.delegates[0].obj.transaction_executor.stop_pool()

    def test6_process_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=1, ctx=self.ctx)

        N_tx= 2
        w_stu =[]
        w_cand = []
        for k in range(N_tx):
            w_stu.append(Wallet())
            w_cand.append(Wallet())

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=mocks.TEST_FOUNDATION_WALLET,
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1_000_000,
                        'to': w_stu[k].verifying_key
                    }
                )
            await asyncio.sleep(12)
            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=w_stu[k],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1338,
                        'to': w_cand[k].verifying_key
                    },
                )
                # await asyncio.sleep(2)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=mocks.TEST_FOUNDATION_WALLET,
                    contract='currency',
                    function='balance_of',
                    kwargs={
                        'account': w_stu[k].verifying_key
                    }
                )
                # await asyncio.sleep(4)

            await asyncio.sleep(4)

            for k in range(N_tx):
                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments=[w_cand[k].verifying_key]
                ), 1338)

            for k in range(N_tx):
                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments= [w_stu[k].verifying_key]
                ), 1_000_000 - 1338 - 0.3)

            # self.assertEqual(network.get_var(
            #     contract='currency',
            #     variable='balances',
            #     arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            # ), 288_090_567 - (1_000_000 + 0.294)* N_tx)

        self.loop.run_until_complete(test())
        network.delegates[0].obj.transaction_executor.stop_pool()

    def test7_process_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        N_tx= 5
        w_stu =[]
        w_cand = []
        for k in range(N_tx):
            w_stu.append(Wallet())
            w_cand.append(Wallet())

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=mocks.TEST_FOUNDATION_WALLET,
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1_000_000,
                        'to': w_stu[k].verifying_key
                    }
                )
            await asyncio.sleep(12)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=w_stu[k],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 111,
                        'to': w_cand[k].verifying_key
                    }
                )

            await asyncio.sleep(4)

            for k in range(N_tx):
                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments= [w_cand[k].verifying_key]
                ), 111)

            # self.assertEqual(network.get_var(
            #     contract='currency',
            #     variable='balances',
            #     arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            # ), 288_090_567 - (1_000_000 + 0.294)* N_tx)

        self.loop.run_until_complete(test())
        network.delegates[0].obj.transaction_executor.stop_pool()

    def test8_process_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        N_tx= 2
        w_stu =[]
        w_cand = []
        for k in range(N_tx):
            w_stu.append(Wallet())
            w_cand.append(Wallet())

        async def test():
            await network.start()
            network.refresh()
            await asyncio.sleep(4)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567)

            await asyncio.sleep(2)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=mocks.TEST_FOUNDATION_WALLET,
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 1_000_000,
                        'to': w_stu[k].verifying_key
                    }
                )
            await asyncio.sleep(12)

            for k in range(N_tx):
                await network.make_and_push_tx(
                    wallet=w_stu[k],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 111,
                        'to': w_cand[k].verifying_key
                    }
                )

            await asyncio.sleep(4)

            for k in range(N_tx):
                self.assertEqual(network.get_var(
                    contract='currency',
                    variable='balances',
                    arguments= [w_cand[k].verifying_key]
                ), 111)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments= [mocks.TEST_FOUNDATION_WALLET.verifying_key]
            ), 288_090_567 - (1_000_000 + 0.294)* N_tx)

        self.loop.run_until_complete(test())
        network.delegates[0].obj.transaction_executor.stop_pool()

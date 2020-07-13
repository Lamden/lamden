from cilantro_ee.nodes.masternode import masternode
from cilantro_ee.nodes import base
from cilantro_ee import router, storage, network, authentication
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto import canonical
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
import zmq.asyncio
import asyncio

from unittest import TestCase


def generate_blocks(number_of_blocks, subblocks=[]):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        if len(subblocks) > i:
            subblock = subblocks[i]
        else:
            subblock = []

        new_block = canonical.block_from_subblocks(
            subblocks=subblock,
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestMasternode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        self.driver = ContractDriver(driver=InMemDriver())
        asyncio.set_event_loop(self.loop)
        self.authenticator = authentication.SocketAuthenticator(
            client=ContractingClient(driver=self.driver),
            ctx=self.ctx)

    def tearDown(self):
        self.authenticator.authenticator.stop()
        self.ctx.destroy()
        self.loop.close()
        self.driver.flush()

    def test_hang_returns_if_not_running(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key],
                'delegates': [Wallet().verifying_key]
            },
            driver=driver
        )

        self.loop.run_until_complete(node.hang())

    def test_hang_until_tx_queue_has_tx(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key],
                'delegates': [Wallet().verifying_key]
            },
            driver=driver
        )

        node.running = True

        async def late_tx(timeout=0.2):
            await asyncio.sleep(timeout)
            node.tx_batcher.queue.append('MOCK TX')

        tasks = asyncio.gather(
            node.hang(),
            late_tx()
        )

        self.loop.run_until_complete(tasks)

    def test_hang_until_nbn_has_block(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key],
                'delegates': [Wallet().verifying_key]
            },
            driver=driver
        )

        node.running = True

        async def late_tx(timeout=0.2):
            await asyncio.sleep(timeout)
            node.new_block_processor.q.append('MOCK BLOCK')

        tasks = asyncio.gather(
            node.hang(),
            late_tx()
        )

        self.loop.run_until_complete(tasks)

    def test_broadcast_new_chain_does_nothing_if_no_tx(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key],
                'delegates': [Wallet().verifying_key]
            },
            driver=driver
        )

        node.client.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=['stu', 'jeff']
        )

    def test_broadcast_new_chain_sends_messages_to_all_peers(self):
        mn_wallet = Wallet()
        mn_bootnode = 'tcp://127.0.0.1:18001'
        mn_router = router.Router(
            wallet=mn_wallet,
            socket_id=mn_bootnode,
            ctx=self.ctx,
            secure=True
        )

        dl_wallet = Wallet()
        dl_bootnode = 'tcp://127.0.0.1:18002'
        dl_router = router.Router(
            wallet=dl_wallet,
            socket_id=dl_bootnode,
            ctx=self.ctx,
            secure=True
        )

        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18003',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [mn_wallet.verifying_key],
                'delegates': [dl_wallet.verifying_key]
            },
            driver=driver
        )

        node.client.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=[mn_wallet.verifying_key]
        )

        node.client.set_var(
            contract='delegates',
            variable='S',
            arguments=['members'],
            value=[dl_wallet.verifying_key]
        )

        node.socket_authenticator.refresh_governance_sockets()

        node.network.peers = {
            mn_wallet.verifying_key: mn_bootnode,
            dl_wallet.verifying_key: dl_bootnode
        }

        node.tx_batcher.queue.append('MOCK TX')

        tasks = asyncio.gather(
            mn_router.serve(),
            dl_router.serve(),
            node.broadcast_new_blockchain_started(),
            stop_server(mn_router, 0.2),
            stop_server(dl_router, 0.2)
        )

        self.loop.run_until_complete(tasks)

    # def test_intermediate_catchup_waits_until_key_in_governance(self):
    #     # A subblock that will have no effect
    #     sbs_1 = {
    #         'transactions': [
    #             {
    #                 'stamps_used': 100,
    #                 'state': [
    #                     {
    #                         'key': 'currency.balances:jeff',
    #                         'value': 10000
    #                     }
    #                 ],
    #                 'transaction': {
    #                     'payload': {
    #                         'sender': 'jeff',
    #                         'nonce': 0,
    #                         'processor': 'stu'
    #                     }
    #                 }
    #             }
    #         ]
    #     }
    #
    #     # A subblock that will add our node to governance
    #     node_wallet = Wallet()
    #     sbs_2 = {
    #         'transactions': [
    #             {
    #                 'stamps_used': 100,
    #                 'state': [
    #                     {
    #                         'key': 'masternodes.S:members',
    #                         'value': [node_wallet.verifying_key]
    #                     }
    #                 ],
    #                 'transaction': {
    #                     'payload': {
    #                         'sender': 'jeff',
    #                         'nonce': 0,
    #                         'processor': 'stu'
    #                     }
    #                 }
    #             }
    #         ]
    #     }
    #
    #     blocks = generate_blocks(2, subblocks=[[sbs_1], [sbs_2]])
    #
    #     driver = ContractDriver(driver=InMemDriver())
    #     node = masternode.Masternode(
    #         socket_base='tcp://127.0.0.1:18003',
    #         ctx=self.ctx,
    #         wallet=node_wallet,
    #         constitution={
    #             'masternodes': [Wallet().verifying_key],
    #             'delegates': [Wallet().verifying_key]
    #         },
    #         driver=driver
    #     )
    #
    #     async def add_block_late(timeout=1):
    #         await asyncio.sleep(timeout)
    #         node.new_block_processor.q.append(blocks[1])
    #
    #     node.new_block_processor.q.append(blocks[0])
    #     node.running = True
    #
    #     tasks = asyncio.gather(
    #         add_block_late(),
    #         node.intermediate_catchup(),
    #
    #     )
    #
    #     self.loop.run_until_complete(tasks)
    #
    #     self.assertTrue(node.running)

    # def test_intermediate_catchup_stops_if_not_running(self):
    #     driver = ContractDriver(driver=InMemDriver())
    #     node_wallet = Wallet()
    #     node = masternode.Masternode(
    #         socket_base='tcp://127.0.0.1:18003',
    #         ctx=self.ctx,
    #         wallet=node_wallet,
    #         constitution={
    #             'masternodes': [Wallet().verifying_key],
    #             'delegates': [Wallet().verifying_key]
    #         },
    #         driver=driver
    #     )
    #
    #     async def stop_late(timeout=1):
    #         await asyncio.sleep(timeout)
    #         node.stop()
    #
    #     tasks = asyncio.gather(
    #         stop_late(),
    #         node.intermediate_catchup(),
    #
    #     )
    #
    #     self.loop.run_until_complete(tasks)
    #
    #     self.assertFalse(node.running)

    def test_send_work_returns_if_no_one_online(self):
        driver = ContractDriver(driver=InMemDriver())
        node_wallet = Wallet()
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18003',
            ctx=self.ctx,
            wallet=node_wallet,
            constitution={
                'masternodes': [Wallet().verifying_key],
                'delegates': [Wallet().verifying_key]
            },
            driver=driver
        )

        r = self.loop.run_until_complete(node.send_work())

        self.assertFalse(r)

    def test_send_work_multicasts_tx_batch_to_delegates(self):
        ips = [
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002',
            'tcp://127.0.0.1:18003'
        ]

        d1w = Wallet()
        d2w = Wallet()
        m1w = Wallet()

        self.authenticator.add_verifying_key(d1w.verifying_key)
        self.authenticator.add_verifying_key(d2w.verifying_key)
        self.authenticator.add_verifying_key(m1w.verifying_key)

        self.authenticator.configure()

        d1_r = router.Router(
            socket_id=ips[0],
            ctx=self.ctx,
            wallet=d1w,
            secure=True
        )
        d2_r = router.Router(
            socket_id=ips[1],
            ctx=self.ctx,
            wallet=d2w,
            secure=True
        )

        d1_q = router.QueueProcessor()
        d2_q = router.QueueProcessor()

        d1_r.add_service(base.WORK_SERVICE, d1_q)
        d2_r.add_service(base.WORK_SERVICE, d2_q)

        node = masternode.Masternode(
            socket_base=ips[2],
            ctx=self.ctx,
            wallet=m1w,
            constitution={
                'masternodes': [m1w.verifying_key],
                'delegates': [d1w.verifying_key, d2w.verifying_key]
            },
            driver=self.driver
        )

        node.network.peers = {
            d1w.verifying_key: ips[0],
            d2w.verifying_key: ips[1],
            m1w.verifying_key: ips[2]
        }

        tasks = asyncio.gather(
            d1_r.serve(),
            d2_r.serve(),
            node.send_work(),
            stop_server(d1_r, 1),
            stop_server(d2_r, 1)
        )

        self.loop.run_until_complete(tasks)

        txb1 = d1_q.q.pop(0)
        txb2 = d2_q.q.pop(0)

        self.assertDictEqual(txb1, txb2)

    def test_new_blockchain_boot_hangs_then_sends_out_broadcast(self):
        mn_wallet = Wallet()
        mn_bootnode = 'tcp://127.0.0.1:18001'
        mn_router = router.Router(
            wallet=mn_wallet,
            socket_id=mn_bootnode,
            ctx=self.ctx,
            secure=True
        )

        dl_wallet = Wallet()
        dl_bootnode = 'tcp://127.0.0.1:18002'
        dl_router = router.Router(
            wallet=dl_wallet,
            socket_id=dl_bootnode,
            ctx=self.ctx,
            secure=True
        )

        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18003',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [mn_wallet.verifying_key],
                'delegates': [dl_wallet.verifying_key]
            },
            driver=driver
        )

        node.client.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=[mn_wallet.verifying_key]
        )

        node.client.set_var(
            contract='delegates',
            variable='S',
            arguments=['members'],
            value=[dl_wallet.verifying_key]
        )

        node.socket_authenticator.refresh_governance_sockets()

        node.network.peers = {
            mn_wallet.verifying_key: mn_bootnode,
            dl_wallet.verifying_key: dl_bootnode
        }

        node.tx_batcher.queue.append('MOCK TX')

        node.running = True

        async def late_tx(timeout=0.2):
            await asyncio.sleep(timeout)
            node.tx_batcher.queue.append('MOCK TX')

        async def late_kill(timeout=1):
            node.running = False

        tasks = asyncio.gather(
            mn_router.serve(),
            dl_router.serve(),
            late_tx(),
            node.new_blockchain_boot(),
            late_kill(),
            stop_server(mn_router, 1),
            stop_server(dl_router, 1)
        )

        self.loop.run_until_complete(tasks)


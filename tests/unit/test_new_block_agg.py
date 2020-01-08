from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.crypto.wallet import Wallet
from tests.utils.constitution_builder import ConstitutionBuilder

import zmq.asyncio
import asyncio
import secrets
from cilantro_ee.storage.state import MetaDataStorage

from cilantro_ee.nodes.masternode.old.block_aggregator import BlockAggregator
from cilantro_ee.nodes.masternode.old.block_aggregator_controller import BlockAggregatorController
from cilantro_ee.sockets.services import _socket
from unittest import TestCase
from tests import random_txs

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.storage.vkbook import VKBook

from cilantro_ee.networking.network import Network
from cilantro_ee.networking.parameters import ServiceType, NetworkParameters

const_builder = ConstitutionBuilder(1, 20, 1, 10, False, False)
book = const_builder.get_constitution()
extract_vk_args(book)


class MockSubscription:
    def __init__(self):
        self.received = []

    def stop(self):
        pass


def random_wallets(n=10):
    return [secrets.token_hex(32) for _ in range(n)]


class TestBlockAggregator(TestCase):
    def setUp(self):
        self.driver = MetaDataStorage()
        self.driver.flush()

        self.ctx = zmq.asyncio.Context()

        submit_vkbook(book, overwrite=True)

    def tearDown(self):
        self.ctx.destroy()

    def test_block_timeout_without_any_quorum_returns_failed_block(self):
        contacts = VKBook()

        b = BlockAggregator(socket_id=_socket('tcp://127.0.0.1:8080'),
                            ctx=self.ctx,
                            block_timeout=0.5, min_quorum=5, max_quorum=10, contacts=contacts)

        # Set this true so that it doesn't hang
        b.pending_block.started = True

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertListEqual(block, [])
        self.assertEqual(kind, 2)

    def test_block_timeout_with_quorum_that_is_90_max_returns_new_block(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        b = BlockAggregator(socket_id=_socket('tcp://127.0.0.1:8080'),
                            ctx=self.ctx, block_timeout=0.5, min_quorum=10, max_quorum=20,
                            current_quorum=14, contacts=contacts)

        b.pending_block.started = True

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash,  b'\x00' * 32, wallets=wallets)
        sigs = [s.to_dict()['signature'] for s in sbcs]

        for i in range(13):
            b.pending_block.contender.add_sbc(wallets[i].verifying_key(), sbcs[i])

        b.pending_block.contender.get_current_quorum_reached()

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 0)
        self.assertTrue(set(sigs).issuperset(set(block[0].to_dict()['signatures'])))

    def test_block_timeout_without_any_quorum_returns_failed_but_use_subscription_service(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets[0:1], as_dict=True)
        sigs = [s['signature'] for s in sbcs]



        b = BlockAggregator(socket_id=_socket('tcp://127.0.0.1:8080'),
                            ctx=self.ctx,
                            block_timeout=0.5,
                            current_quorum=12,
                            min_quorum=10,
                            max_quorum=20,
                            contacts=contacts)

        msg = Message.get_signed_message_packed_2(wallet=wallets[0],
                                                  msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                  **sbcs[0])
        b.async_queue.q.append((msg, 0))



        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 2)
        self.assertTrue(set(sigs).issuperset(set(block[0].to_dict()['signatures'])))

    def test_block_new_if_all_sbc_are_in_sub_received(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets, as_dict=True)
        sigs = [s['signature'] for s in sbcs]

        b = BlockAggregator(socket_id=_socket('tcp://127.0.0.1:8080'),
                            ctx=self.ctx,
                            block_timeout=0.5,
                            current_quorum=20,
                            min_quorum=10,
                            max_quorum=20,
                            contacts=contacts)

        for i in range(len(sbcs)):
            msg = Message.get_signed_message_packed_2(wallet=wallets[i],
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbcs[i])
            b.async_queue.q.append((msg, 0))

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 0)
        self.assertTrue(set(sigs).issuperset(set(block[0].to_dict()['signatures'])))

    def test_block_skip_if_all_sbc_are_in_sub_received_and_empty(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        b = BlockAggregator(socket_id=_socket('tcp://127.0.0.1:8080'),
                            ctx=self.ctx,
                            block_timeout=0.5,
                            min_quorum=10,
                            max_quorum=20,
                            current_quorum=20,
                            contacts=contacts)

        for wallet in wallets:
            _, merkle_proof = Message.get_message_packed(
                MessageType.MERKLE_PROOF,
                hash=input_hash,
                signer=wallet.verifying_key(),
                signature=wallet.sign(input_hash))

            msg = Message.get_signed_message_packed_2(wallet=wallet,
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      resultHash=input_hash,
                                                      inputHash=input_hash,
                                                      merkleLeaves=[],
                                                      signature=merkle_proof,
                                                      transactions=[],
                                                      subBlockNum=0,
                                                      prevBlockHash=b'\x00' * 32)

            b.async_queue.q.append((msg, 0))

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 1)
        self.assertEqual(len(set(block[0].to_dict()['merkleLeaves'])), 0)

    def test_block_fail_if_consensus_not_possible_but_hash_sbcs(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        sigs = []

        b = BlockAggregator(socket_id=_socket('tcp://127.0.0.1:8080'),
                            ctx=self.ctx,
                            block_timeout=0.5,
                            min_quorum=10,
                            max_quorum=20,
                            current_quorum=20,
                            contacts=contacts)

        for wallet in wallets:
            sbc = random_txs.sbc_from_txs(input_hash, b'\x00' * 32, w=wallet)
            sigs.append(sbc.to_dict()['signature'])

            msg = Message.get_signed_message_packed_2(wallet=wallet,
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbc.to_dict())

            b.async_queue.q.append((msg, 0))

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 2)
        self.assertTrue(set(sigs).issuperset(set(block[0].to_dict()['signatures'])))


class TestBlockAggregatorController(TestCase):
    def setUp(self):
        self.driver = MetaDataStorage()
        self.driver.flush()

        submit_vkbook(book, overwrite=True)

        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_process_blocks_new_block_stores(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        wallets = wallets[:contacts.delegate_quorum_max]

        w = const_builder.get_mn_wallets()[0]
        bc = BlockAggregatorController(wallet=w,
                                       socket_base='tcp://127.0.0.1',
                                       vkbook=contacts,
                                       ctx=self.ctx,
                                       block_timeout=1)

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets, as_dict=True)

        for i in range(len(sbcs)):
            msg = Message.get_signed_message_packed_2(wallet=wallets[i],
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbcs[i])
            bc.aggregator.async_queue.q.append((msg, 0))

        bc.driver.drop_collections()
        bc.running = True

        async def stop():
            await asyncio.sleep(1)
            bc.stop()

        async def recieve():
            addr = NetworkParameters().resolve(socket_base='tcp://127.0.0.1',
                                               service_type=ServiceType.BLOCK_AGGREGATOR)
            s = self.ctx.socket(zmq.SUB)
            s.setsockopt(zmq.SUBSCRIBE, b'')
            s.connect(str(addr))
            m = await s.recv()
            return m

        loop = asyncio.get_event_loop()

        tasks = asyncio.gather(
            stop(),
            bc.aggregator.start(),
            bc.process_blocks(),
            recieve()
        )

        loop.run_until_complete(tasks)

        self.assertEqual(bc.driver.get_last_n(1, bc.driver.BLOCK)[0]['blockNum'], 1)

    def test_process_block_not_new_does_not_store(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        w = const_builder.get_mn_wallets()[0]
        bc = BlockAggregatorController(wallet=w,
                                       socket_base='tcp://127.0.0.1',
                                       vkbook=contacts,
                                       ctx=self.ctx,
                                       block_timeout=1)

        for wallet in wallets:
            _, merkle_proof = Message.get_message_packed(
                MessageType.MERKLE_PROOF,
                hash=input_hash,
                signer=wallet.verifying_key(),
                signature=wallet.sign(input_hash))

            msg = Message.get_signed_message_packed_2(wallet=wallet,
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      resultHash=input_hash,
                                                      inputHash=input_hash,
                                                      merkleLeaves=[],
                                                      signature=merkle_proof,
                                                      transactions=[],
                                                      subBlockNum=0,
                                                      prevBlockHash=b'\x00' * 32)

            bc.aggregator.async_queue.q.append((msg, 0))

        bc.driver.drop_collections()
        bc.running = True

        async def stop():
            await asyncio.sleep(2)
            bc.stop()

        async def recieve():
            addr = NetworkParameters().resolve(socket_base='tcp://127.0.0.1',
                                               service_type=ServiceType.BLOCK_AGGREGATOR)
            s = self.ctx.socket(zmq.SUB)
            s.setsockopt(zmq.SUBSCRIBE, b'')
            s.connect(str(addr))
            m = await s.recv()
            return m

        loop = asyncio.get_event_loop()

        tasks = asyncio.gather(
            stop(),
            bc.process_blocks(),
            bc.aggregator.start(),
            recieve(),
        )

        loop.run_until_complete(tasks)

        self.assertEqual(bc.driver.get_last_n(1, bc.driver.BLOCK), [])

    def test_process_block_publishes_new_block_notification(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        wallets = wallets[:contacts.delegate_quorum_max]

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets, as_dict=True)

        w = const_builder.get_mn_wallets()[0]
        bc = BlockAggregatorController(wallet=w,
                                       socket_base='tcp://127.0.0.1',
                                       vkbook=contacts,
                                       ctx=self.ctx,
                                       block_timeout=0.5)

        for i in range(len(sbcs)):
            msg = Message.get_signed_message_packed_2(wallet=wallets[i],
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbcs[i])
            bc.aggregator.async_queue.q.append((msg, 0))

        bc.driver.drop_collections()
        bc.running = True

        async def stop():
            await asyncio.sleep(1)
            bc.stop()

        async def recieve():
            addr = NetworkParameters().resolve(socket_base='tcp://127.0.0.1',
                                               service_type=ServiceType.BLOCK_AGGREGATOR)
            s = self.ctx.socket(zmq.SUB)
            s.setsockopt(zmq.SUBSCRIBE, b'')
            s.connect(str(addr))
            m = await s.recv()
            return m

        loop = asyncio.get_event_loop()

        tasks = asyncio.gather(
            stop(),
            bc.process_sbcs_from_delegates(),
            bc.aggregator.start(),
            recieve(),
        )

        _, _, _, m = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(m)

        self.assertEqual(msg.blockNum, 1)

    def test_process_block_publishes_skip_block_notification(self):
        s = MockSubscription()
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        wallets = wallets[:contacts.delegate_quorum_max]

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets, as_dict=True)

        w = const_builder.get_mn_wallets()[0]
        bc = BlockAggregatorController(wallet=w,
                                       socket_base='tcp://127.0.0.1',
                                       vkbook=contacts,
                                       ctx=self.ctx,
                                       block_timeout=0.5)

        for wallet in wallets:
            _, merkle_proof = Message.get_message_packed(
                MessageType.MERKLE_PROOF,
                hash=input_hash,
                signer=wallet.verifying_key(),
                signature=wallet.sign(input_hash))

            msg = Message.get_signed_message_packed_2(wallet=wallet,
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      resultHash=input_hash,
                                                      inputHash=input_hash,
                                                      merkleLeaves=[],
                                                      signature=merkle_proof,
                                                      transactions=[],
                                                      subBlockNum=0,
                                                      prevBlockHash=b'\x00' * 32)

            bc.aggregator.async_queue.q.append((msg, 0))

        bc.driver.drop_collections()
        bc.aggregator.subblock_subscription_service = s
        bc.running = True

        async def stop():
            await asyncio.sleep(1)
            bc.stop()

        async def recieve():
            addr = NetworkParameters().resolve(socket_base='tcp://127.0.0.1',
                                               service_type=ServiceType.BLOCK_AGGREGATOR)
            s = self.ctx.socket(zmq.SUB)
            s.setsockopt(zmq.SUBSCRIBE, b'')
            s.connect(str(addr))
            m = await s.recv()
            return m

        loop = asyncio.get_event_loop()

        tasks = asyncio.gather(
            stop(),
            bc.process_blocks(),
            recieve(),
            bc.aggregator.start()
        )

        _, _, m, _ = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(m)

        self.assertEqual(msg.blockNum, 0)

    def test_start_starts_aggregator_subscribes_to_all_delegates_in_socket_book(self):
        # Start several mock delegates
        w = Wallet()

        # Set the network peers to the current delegates and mock a fake port
        wallets = [w.verifying_key().hex() for w in const_builder.get_del_wallets()]
        contacts = VKBook()

        peers = {}

        for i in range(len(wallets)):
            peers[wallets[i]] = 'tcp://127.0.0.{}'.format(i + 2)

        # Build network to start and serve peer data
        n = Network(wallet=w, ctx=self.ctx, socket_base='tcp://127.0.0.1')
        n.table.peers = peers

        bc = BlockAggregatorController(wallet=w,
                                       socket_base='tcp://127.0.0.1',
                                       vkbook=contacts,
                                       ctx=self.ctx,
                                       block_timeout=1)

        async def run():
            asyncio.ensure_future(n.start(discover=False))
            await bc.start()
            bc.stop()
            n.stop()

        loop = asyncio.get_event_loop()

        loop.run_until_complete(run())

        # Test that all peers are now in the subscription service
        self.assertSetEqual(set(['{}:{}'.format(v, 10011) for v in peers.values()]),
                            set(bc.aggregator.subblock_subscription_service.subscriptions.keys()))

from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.core.crypto.wallet import Wallet
from tests.utils.constitution_builder import ConstitutionBuilder

import zmq.asyncio
import asyncio
import secrets
from cilantro_ee.services.storage.state import MetaDataStorage

from cilantro_ee.nodes.masternode.block_aggregator import TransactionBatcherInformer, Block, BlockAggregator, BlockAggregatorController
from cilantro_ee.core.messages.message import Message, MessageType
from cilantro_ee.core.sockets.services import _socket
from unittest import TestCase
from tests import random_txs
from copy import deepcopy

from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup, BlockContender

ctx = zmq.asyncio.Context()
const_builder = ConstitutionBuilder(1, 20, 1, 10, False, False)
book = const_builder.get_constitution()
extract_vk_args(book)
submit_vkbook(book, overwrite=True)


class TestTransactionBatcherInformer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        # self.const_builder = ConstitutionBuilder(3, 3, False, False)
        # submit_vkbook(self.const_builder.get_constitution())
        # self.ctx = ctx

    def tearDown(self):
        self.ctx.destroy()

    def test_send_ready(self):
        w = Wallet()
        t = TransactionBatcherInformer(ctx=self.ctx, wallet=w)

        async def recieve():
            s = self.ctx.socket(zmq.PAIR)
            s.connect('ipc:///tmp/tx_batch_informer')
            m = await s.recv()
            return m

        tasks = asyncio.gather(
            recieve(),
            t.send_ready(),
        )

        loop = asyncio.get_event_loop()
        blob, _ = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(blob)

        self.assertEqual(MessageType.READY, msg_type)

    def test_send_hashes_same_list_of_hashes(self):
        w = Wallet()
        t = TransactionBatcherInformer(ctx=self.ctx, wallet=w)

        async def recieve():
            s = self.ctx.socket(zmq.PAIR)
            s.connect('ipc:///tmp/tx_batch_informer')
            m = await s.recv()
            return m

        tasks = asyncio.gather(
            recieve(),
            t.send_burn_input_hashes([b'a', b'b', b'c', b'd']),
        )

        loop = asyncio.get_event_loop()
        blob, _ = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(blob)

        self.assertEqual(msg_type, MessageType.BURN_INPUT_HASHES)
        self.assertListEqual([i for i in msg.inputHashes], [b'a', b'b', b'c', b'd'])


class TestBlock(TestCase):
    pass


class MockSubscription:
    def __init__(self):
        self.received = []


def random_wallets(n=10):
    return [secrets.token_hex(32) for _ in range(n)]


class TestBlockAggregator(TestCase):
    def setUp(self):
        self.driver = MetaDataStorage()
        self.driver.flush()
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_block_timeout_without_any_quorum_returns_failed_block(self):
        contacts = VKBook()

        b = BlockAggregator(subscription=MockSubscription(), block_timeout=0.5, min_quorum=5, max_quorum=10, contacts=contacts)

        # Set this true so that it doesn't hang
        b.pending_block.started = True

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertListEqual(block, [])
        self.assertEqual(kind, 2)

    def test_block_timeout_with_quorum_that_is_90_max_returns_new_block(self):
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        b = BlockAggregator(subscription=MockSubscription(), block_timeout=0.5, min_quorum=10, max_quorum=20,
                            current_quorum=14, contacts=contacts)

        b.pending_block.started = True

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash,  b'\x00' * 32, wallets=wallets)

        for i in range(13):
            b.pending_block.contender.add_sbc(wallets[i].verifying_key(), sbcs[i])

        b.pending_block.contender.get_current_quorum_reached()

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 0)

    def test_block_timeout_without_any_quorum_returns_failed_but_use_subscription_service(self):
        s = MockSubscription()

        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets[0:1], as_dict=True)

        msg = Message.get_signed_message_packed_2(wallet=wallets[0],
                                                  msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                  **sbcs[0])

        s.received.append((msg, 0))

        b = BlockAggregator(subscription=s,
                            block_timeout=0.5,
                            current_quorum=12,
                            min_quorum=10,
                            max_quorum=20,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 2)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())

    def test_block_new_if_all_sbc_are_in_sub_received(self):
        s = MockSubscription()

        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets, as_dict=True)

        for i in range(len(sbcs)):
            msg = Message.get_signed_message_packed_2(wallet=wallets[i],
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbcs[i])
            s.received.append((msg, 0))

        b = BlockAggregator(subscription=s,
                            block_timeout=0.5,
                            current_quorum=20,
                            min_quorum=10,
                            max_quorum=20,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 0)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())

    def test_block_skip_if_all_sbc_are_in_sub_received_and_empty(self):
        s = MockSubscription()

        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

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

            s.received.append((msg, 0))

        b = BlockAggregator(subscription=s,
                            block_timeout=0.5,
                            min_quorum=10,
                            max_quorum=20,
                            current_quorum=20,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind,1)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())

    def test_block_fail_if_consensus_not_possible_but_hash_sbcs(self):
        s = MockSubscription()

        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        for wallet in wallets:

            sbc = random_txs.sbc_from_txs(input_hash, b'\x00' * 32, w=wallet)
            msg = Message.get_signed_message_packed_2(wallet=wallet,
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbc.to_dict())

            s.received.append((msg, 0))

        b = BlockAggregator(subscription=s,
                            block_timeout=0.5,
                            min_quorum=10,
                            max_quorum=20,
                            current_quorum=20,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 2)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())


class TestBlockAggregatorController(TestCase):
    def setUp(self):
        self.driver = MetaDataStorage()
        self.driver.flush()
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_process_blocks_new_block_stores(self):
        # setup
        s = MockSubscription()
        wallets = const_builder.get_del_wallets()
        contacts = VKBook()

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets, as_dict=True)

        for i in range(len(sbcs)):
            msg = Message.get_signed_message_packed_2(wallet=wallets[i],
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbcs[i])
            s.received.append((msg, 0))

        w = const_builder.get_mn_wallets()[0]
        bc = BlockAggregatorController(wallet=w, socket_base='tcp://127.0.0.1', vkbook=contacts, ctx=self.ctx)

        bc.aggregator.subblock_subscription_service = s
        bc.running = True

        async def stop():
            await asyncio.sleep(1)
            bc.running = False

        loop = asyncio.get_event_loop()

        tasks = asyncio.gather(
            bc.process_blocks(),
            stop()
        )

        loop.run_until_complete(tasks)

        # use driver to read the stored block
        # compare it with the generated block
        pass

    def test_process_block_not_new_does_not_store(self):
        pass

    def test_process_block_sends_burn_input_hashes(self):
        pass

    def test_process_block_publishes_new_block_notification(self):
        pass

    def test_start_starts_aggregator(self):
        pass

    def test_start_sends_ready_from_informer(self):
        pass

    def test_start_publishes_ready(self):
        pass

    def test_serialize_block_new_to_new_block_notification(self):
        pass

    def test_serialize_block_skip_to_new_block_notification(self):
        pass

    def test_serialize_block_fail_to_new_block_notification(self):
        pass
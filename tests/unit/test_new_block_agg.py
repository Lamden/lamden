from cilantro_ee.nodes.masternode.new_ba import TransactionBatcherInformer, Block, BlockAggregator, BlockAggregatorController
from cilantro_ee.core.sockets.services import _socket
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.messages.message import Message, MessageType
from cilantro_ee.services.storage.vkbook import PhoneBook, VKBook
from unittest import TestCase
import zmq.asyncio
import asyncio
import secrets
from tests import random_txs

from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup, BlockContender

class TestTransactionBatcherInformer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_send_ready(self):
        w = Wallet()
        t = TransactionBatcherInformer(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=self.ctx, wallet=w)

        async def recieve():
            s = self.ctx.socket(zmq.PAIR)
            s.connect('tcp://127.0.0.1:8888')
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
        t = TransactionBatcherInformer(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=self.ctx, wallet=w)

        async def recieve():
            s = self.ctx.socket(zmq.PAIR)
            s.connect('tcp://127.0.0.1:8888')
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
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_block_timeout_without_any_quorum_returns_failed_block(self):
        b = BlockAggregator(subscription=MockSubscription(), block_timeout=0.5, min_quorum=5, max_quorum=10)

        # Set this true so that it doesn't hang
        b.pending_block.started = True

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertListEqual(block, [])
        self.assertEqual(kind, 2)

    def test_block_timeout_with_quorum_that_is_90_max_returns_new_block(self):
        wallets = [Wallet() for _ in range(20)]

        contacts = VKBook(delegates=[w.verifying_key() for w in wallets],
                          masternodes=['A' * 64])

        b = BlockAggregator(subscription=MockSubscription(), block_timeout=0.5, min_quorum=10, max_quorum=20,
                            subblocks_per_block=1, builders_per_block=1, contacts=contacts)

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

        wallets = [Wallet() for _ in range(20)]

        contacts = VKBook(delegates=[w.verifying_key() for w in wallets],
                          masternodes=['A' * 64])

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets[0:1], as_dict=True)

        msg = Message.get_signed_message_packed_2(wallet=wallets[0],
                                                  msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                  **sbcs[0])

        s.received.append((msg, 0))

        b = BlockAggregator(subscription=s,
                            block_timeout=0.5,
                            min_quorum=10,
                            max_quorum=20,
                            current_quorum=12,
                            subblocks_per_block=1,
                            builders_per_block=1,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 2)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())

    def test_block_new_if_all_sbc_are_in_sub_received(self):
        s = MockSubscription()

        wallets = [Wallet() for _ in range(20)]

        contacts = VKBook(delegates=[w.verifying_key() for w in wallets],
                          masternodes=['A' * 64])

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, b'\x00' * 32, wallets=wallets, as_dict=True)

        for i in range(len(sbcs)):
            msg = Message.get_signed_message_packed_2(wallet=wallets[i],
                                                      msg_type=MessageType.SUBBLOCK_CONTENDER,
                                                      **sbcs[i])
            s.received.append((msg, 0))

        b = BlockAggregator(subscription=s,
                            block_timeout=0.5,
                            min_quorum=10,
                            max_quorum=20,
                            current_quorum=20,
                            subblocks_per_block=1,
                            builders_per_block=1,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 0)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())

    def test_block_skip_if_all_sbc_are_in_sub_received_and_empty(self):
        s = MockSubscription()

        wallets = [Wallet() for _ in range(20)]

        contacts = VKBook(delegates=[w.verifying_key() for w in wallets],
                          masternodes=['A' * 64])

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
                                                      subBlockIdx=0,
                                                      prevBlockHash=b'\x00' * 32)

            s.received.append((msg, 0))

        b = BlockAggregator(subscription=s,
                            block_timeout=0.5,
                            min_quorum=10,
                            max_quorum=20,
                            current_quorum=20,
                            subblocks_per_block=1,
                            builders_per_block=1,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind,1)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())

    def test_block_fail_if_consensus_not_possible_but_hash_sbcs(self):
        s = MockSubscription()

        wallets = [Wallet() for _ in range(20)]

        contacts = VKBook(delegates=[w.verifying_key() for w in wallets],
                          masternodes=['A' * 64])

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
                            subblocks_per_block=1,
                            builders_per_block=1,
                            contacts=contacts)

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertEqual(kind, 2)
        self.assertEqual(block[0].to_dict(), b.pending_block.contender.get_sb_data()[0].to_dict())


class TestBlockAggregatorController(TestCase):
    pass
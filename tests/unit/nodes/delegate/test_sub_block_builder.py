from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')
#
from cilantro_ee.logger.base import get_logger
# from cilantro_ee.constants.system_config import *
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int
from cilantro_ee.utils.hasher import Hasher
#
from contracting.db.cr.client import SubBlockClient
from contracting.db.cr.callback_data import ExecutionData, SBData
#
# from cilantro_ee.nodes.delegate.block_manager import IPC_IP, IPC_PORT
from cilantro_ee.nodes.delegate.sub_block_builder import SubBlockBuilder, SubBlockManager, NextBlockState
#
from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.transaction.batch import TransactionBatch, build_test_transaction_batch
from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender, SubBlockContenderBuilder
from cilantro_ee.messages.transaction.data import TransactionData, TransactionDataBuilder
from cilantro_ee.messages.transaction.contract import ContractTransactionBuilder
from cilantro_ee.messages.signals.delegate import MakeNextBlock
from cilantro_ee.messages.signals.node import Ready
from cilantro_ee.messages.block_data.notification import FailedBlockNotification
#
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock
from cilantro_ee.storage.vkbook import PhoneBook, VKBook
from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.constants.testnet import *
from cilantro_ee.storage.vkbook import PhoneBook
import asyncio
import time
from cilantro_ee.constants.testnet import TESTNET_DELEGATES, TESTNET_MASTERNODES
from cilantro_ee.protocol import wallet
#
_log = get_logger("TestSubBlockBuilder")
#
TEST_IP = '127.0.0.1'
# DELEGATE_SK = TESTNET_DELEGATES[0]['sk']
DELEGATE_SK = PhoneBook.delegates[0]

IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967
#
# MN_SK1 = TESTNET_MASTERNODES[0]['sk']
# MN_SK2 = TESTNET_MASTERNODES[1]['sk']
MN_SK1 = PhoneBook.masternodes[0]
MN_SK2 = PhoneBook.masternodes[1]
MN_SK1 = TESTNET_MASTERNODES[0]['sk']
MN_SK2 = TESTNET_MASTERNODES[1]['sk']

#
#
class SBBTester:

    @staticmethod
    def test(func):
        @mock.patch("cilantro_ee.protocol.multiprocessing.worker.asyncio")
        @mock.patch("cilantro_ee.protocol.multiprocessing.worker.SocketManager")
        @mock.patch("cilantro_ee.nodes.delegate.block_manager.asyncio")
        @mock.patch("cilantro_ee.nodes.delegate.block_manager.SubBlockBuilder.run")
        def _func(*args, **kwargs):
            return func(*args, **kwargs)
        return _func

    @staticmethod
    def send_ipc_to_sbb(sbb: SubBlockBuilder, msg: MessageBase):
        message_type = MessageBase.registry[type(msg)]
        frames = [int_to_bytes(message_type), msg.serialize()]
        sbb.handle_ipc_msg(frames)

    @staticmethod
    def send_sub_to_sbb(sbb: SubBlockBuilder, envelope: Envelope, handler_key, filter_frame=b''):
        frames = [filter_frame, envelope.serialize()]
        sbb.handle_sub_msg(frames, handler_key)

    @staticmethod
    def create_tx_batch_env(num_txs: int, env_signing_key: str) -> Envelope:
        tx_batch = build_test_transaction_batch(num_tx=num_txs)
        return Envelope.create_from_message(message=tx_batch, signing_key=env_signing_key)

    @staticmethod
    def send_tx_batch_to_sbb(sbb: SubBlockBuilder, handler_key, num_txs: int, masternode_sk: str=MN_SK1):
        batch = SBBTester.create_tx_batch_env(num_txs=num_txs, env_signing_key=masternode_sk)
        SBBTester.send_sub_to_sbb(sbb, envelope=batch, handler_key=handler_key)


class TestSubBlockBuilder(TestCase):

    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 8)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 8)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    def test_create_sub_sockets(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)

        self.assertEqual(len(sbb.sb_managers), 8)

    def run_async(self, loop, period=1.0):
        async def asyncio_sucks():
            await asyncio.sleep(period)

        loop.run_until_complete(asyncio_sucks())

    def run_loops(self, *loops, period=1.0):
        async def asyncio_sucks():
            await asyncio.sleep(period)

        master_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(master_loop)
        futs = []
        for l in loops:
            futs.append(asyncio.ensure_future(l.run_until_complete(asyncio_sucks())))

        master_loop.run_until_complete(asyncio.gather(futs))



    @SBBTester.test
    def test_create_empty_sbc(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)

        PhoneBook = VKBook(delegates=[sbb.verifying_key], masternodes=[TESTNET_MASTERNODES[0]['vk']])

        input_hash = 'A' * 64
        sbb_idx = 0
        sb_data = SBData(input_hash, [])
        sbb._send_msg_over_ipc = MagicMock()

        sbb._create_empty_sbc(sb_data)
        sbb._send_msg_over_ipc.assert_called()
        empty_sbc = sbb._send_msg_over_ipc.call_args[0][0]
        self.assertTrue(isinstance(empty_sbc, SubBlockContender))
        self.assertEqual(empty_sbc.input_hash, input_hash)
        self.assertEqual(empty_sbc.sb_index, sbb_idx)
        self.assertTrue(empty_sbc.is_empty)


    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_one_sb_recv_empty_tx_bag(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        self.assertEqual(len(sbb.sb_managers), 1)

        # Send an empty TX batch. This should get queued up as the SBB doesnt have a MakeNextBlock msg yet
        empty_tx_batch_env = SBBTester.create_tx_batch_env(num_txs=0, env_signing_key=MN_SK1)
        SBBTester.send_sub_to_sbb(sbb, envelope=empty_tx_batch_env, handler_key=0)
        self.assertEqual(len(sbb.sb_managers[0].pending_txs), 1)

        # Now, send a MakeNextBlock notif. This should trigger an empty subblock to be built and sent over IPC to BM
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_sub_msg_with_make_next_block_notification_calls_handle_ipc_msg(self, *args):
        """
        Tests handle_ipc_msg correctly calls handle_new_block when a NewBlockNotification is received
        """

        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)

        PhoneBook = VKBook(delegates=[sbb.verifying_key], masternodes=[TESTNET_MASTERNODES[0]['vk']])

        sbb._send_msg_over_ipc = MagicMock()

        self.assertTrue(len(sbb.sb_managers) == 1)

        # Mock Envelope.from_bytes to return a mock envelope of our choosing
        tx_batch_env = SBBTester.create_tx_batch_env(num_txs=4, env_signing_key=MN_SK1)
        # print("print tsns")
        # print(tx_batch_env.message.transactions[0])
        SBBTester.send_sub_to_sbb(sbb, envelope=tx_batch_env, handler_key=0)


        sbb._make_next_sub_block()

        self.run_async(sbb.loop, 2)
        assert sbb._send_msg_over_ipc.called
        assert sbb._send_msg_over_ipc.call_count == 2
        msg = sbb._send_msg_over_ipc.call_args[1][0][0]
        print("raghu msg = {}".format(msg))
        self.assertTrue(isinstance(msg, SubBlockContender))
        self.assertFalse(msg.is_empty)


    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_handle_new_block_signal_calls_make_next_sub_block(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        sbb._make_next_sub_block = MagicMock()

        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        sbb._make_next_sub_block.assert_called_once()


    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_align_input_hash_signal(self, *args):
        TRANSACTIONS_PER_SUB_BLOCK = 4
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)



        self.assertEqual(len(sbb.sb_managers), 1)
        sbb._send_msg_over_ipc = MagicMock()
        sbb._create_empty_sbc = MagicMock()
        sbb._create_sbc_from_batch = MagicMock()

        # send it 4 blocks w/ 4 txns
        ib_hashes = []
        num_txs = TRANSACTIONS_PER_SUB_BLOCK
        for i in range(4):
            tx_batch = SBBTester.create_tx_batch_env(num_txs=num_txs, env_signing_key=MN_SK1)
            input_hash = Hasher.hash(tx_batch)
            ib_hashes.append(input_hash)
            SBBTester.send_sub_to_sbb(sbb, envelope=tx_batch, handler_key=0)

        # Now, send a MakeNextBlock notif. This should trigger an empty subblock to be built and sent over IPC to BM
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        self.run_async(sbb.loop, 2)
        # should receive a _new subblock for input 0 and assert its input_hash is same as the one above
        # SBBTester.send_ipc_to_sbb(sbb, make_next_block)
        sbb._create_sbc_from_batch.assert_called_once()
        sb = sbb._create_sbc_from_batch.call_args[0][0]
        self.assertEqual(sb.input_hash, ib_hashes[0])

        # need to update the test case here
        # send align notification for input hash # 3
        # message = AlignInputHash.create(ib_hashes[2], 0)
        # SBBTester.send_ipc_to_sbb(sbb, message)
        # SBBTester.send_ipc_to_sbb(sbb, make_next_block)
        # self.run_async(sbb.loop, 2)
        # should receive a _new subblock for input 4
        # sbb._create_sbc_from_batch.assert_called()
        # sb = sbb._create_sbc_from_batch.call_args[0][0]
        # self.assertEqual(sb.input_hash, ib_hashes[3])


    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_single_tx_batch_adds_to_queue(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        # Note we do not send a MakeNextBlockNotifcation

        # Before we SBB receives any tx batches, we expect his (one) manager to be empty
        self.assertEqual(len(sbb.sb_managers), 1)
        self.assertEqual(len(sbb.sb_managers[0].pending_txs), 0)

        # Send first TX bag in. This should get queued.
        tx_batch = SBBTester.create_tx_batch_env(num_txs=4, env_signing_key=MN_SK1)
        SBBTester.send_sub_to_sbb(sbb, envelope=tx_batch, handler_key=0)

        self.assertEqual(len(sbb.sb_managers[0].pending_txs), 1)
        self.assertEqual(sbb.sb_managers[0].pending_txs.popleft(), tx_batch)

    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_double_tx_batch_builds_sbb(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        sbb._execute_next_sb = MagicMock()

        # First, fake a MakeNextBlock msg from BlockManager
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        # Send first TX bag in. Since w sent a MakeNextBlock notif, this should trigger a block construction
        tx_batch_env = SBBTester.create_tx_batch_env(num_txs=4, env_signing_key=MN_SK1)
        input_hash1 = Hasher.hash(tx_batch_env)
        SBBTester.send_sub_to_sbb(sbb, envelope=tx_batch_env, handler_key=0)

        # sbb._execute_next_sb.assert_called_with(input_hash1, tx_batch_env.message, 0)
        sbb._execute_next_sb.assert_called()


    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_create_sbc_from_batch(self, *args):
        num_txs = 4
        input_hash = 'A' * 64
        sbb_idx = 0
        # create a few contract txs
        contract_txs, states, statuses = [], [], []
        for _ in range(num_txs):
            contract_txs.append(ContractTransactionBuilder.create_currency_tx('A' * 64, 'B' * 64, 100))
            states.append('SET MONEY OVER 9000')
            statuses.append('SUCC')

        sb_rep = [(c, status, state) for c, state, status, in zip(contract_txs, states, statuses)]

        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)

        PhoneBook = VKBook(delegates=[sbb.verifying_key], masternodes=[TESTNET_MASTERNODES[0]['vk']])

        sbb._send_msg_over_ipc = MagicMock()

        exec_data = []
        for i in range(len(contract_txs)):
            exec_data.append(ExecutionData(contract=contract_txs[i], status=statuses[i],
                                           response='', state=states[i], stamps=10000))

        sb_data = SBData(input_hash=input_hash, tx_data=exec_data)

        sbb._create_sbc_from_batch(sb_data)

        # TODO assert tis was called with the expected SBC passed in
        sbb._send_msg_over_ipc.assert_called()

    @SBBTester.test
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_execute_two_bags_one_builder(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)

        _, vk_1 = wallet.new(bytes.fromhex(MN_SK1))
        PhoneBook = VKBook(delegates=[sbb.verifying_key], masternodes=[vk_1])

        sbb._create_sbc_from_batch = MagicMock()

        # send intital make next blk notif
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        tx_batch_env = SBBTester.create_tx_batch_env(10, MN_SK1)
        SBBTester.send_sub_to_sbb(sbb, tx_batch_env, handler_key=0)

        # ANOTHER ONE
        tx_batch_env = SBBTester.create_tx_batch_env(10, MN_SK1)
        SBBTester.send_sub_to_sbb(sbb, tx_batch_env, handler_key=0)

        self.run_async(sbb.loop, 2)

        # now send him a make next blk
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        # make sure he called _created_sbc as a result of inputing a bag
        sbb._create_sbc_from_batch.assert_called_once()

        self.run_async(sbb.loop, 2)

        # yet ANOTHER ONE
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        self.run_async(sbb.loop, 2)
        self.assertEqual(sbb._create_sbc_from_batch.call_count, 2)

    # @SBBTester.test
    # # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    # def test_execute_two_bags_two_builder(self, *args):
    #     sbb1 = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
    #     sbb1._create_sbc_from_batch = MagicMock()
    #
    #     sbb2 = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
    #     sbb2._create_sbc_from_batch = MagicMock()
    #
    #     # send intital make next blk notif
    #     make_next_block = MakeNextBlock.create()
    #     SBBTester.send_ipc_to_sbb(sbb1, make_next_block)
    #     SBBTester.send_ipc_to_sbb(sbb2, make_next_block)
    #
    #     # THE FIRST
    #     tx_batch_env1 = SBBTester.create_tx_batch_env(10, MN_SK1)
    #     SBBTester.send_sub_to_sbb(sbb1, tx_batch_env1, handler_key=0)
    #     tx_batch_env2 = SBBTester.create_tx_batch_env(10, MN_SK2)
    #     SBBTester.send_sub_to_sbb(sbb2, tx_batch_env2, handler_key=0)
    #
    #     self.run_async(sbb1.loop, 2)
    #     self.run_async(sbb2.loop, 2)
    #
    #     # now send him a make next blk
    #     make_next_block = MakeNextBlock.create()
    #     SBBTester.send_ipc_to_sbb(sbb1, make_next_block)
    #     SBBTester.send_ipc_to_sbb(sbb2, make_next_block)
    #
    #     self.run_async(sbb1.loop, 2)
    #     self.run_async(sbb2.loop, 2)
    #
    #     # make sure he called _created_sbc as a result of inputing a bag
    #     sbb1._create_sbc_from_batch.assert_called_once()
    #     sbb2._create_sbc_from_batch.assert_called_once()
    #
    # @SBBTester.test
    # # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    # def test_execute_four_bags_two_builder(self, *args):
    #     sbb1 = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
    #     sbb1._create_sbc_from_batch = MagicMock()
    #
    #     sbb2 = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
    #     sbb2._create_sbc_from_batch = MagicMock()
    #
    #     # send intital make next blk notif
    #     make_next_block = MakeNextBlock.create()
    #     SBBTester.send_ipc_to_sbb(sbb1, make_next_block)
    #     SBBTester.send_ipc_to_sbb(sbb2, make_next_block)
    #
    #     tx_batch_env2 = SBBTester.create_tx_batch_env(20, MN_SK2)
    #     SBBTester.send_sub_to_sbb(sbb2, tx_batch_env2, handler_key=0)
    #
    #     # THE FIRST
    #     tx_batch_env1 = SBBTester.create_tx_batch_env(10, MN_SK1)
    #     SBBTester.send_sub_to_sbb(sbb1, tx_batch_env1, handler_key=0)
    #     tx_batch_env2 = SBBTester.create_tx_batch_env(20, MN_SK2)
    #     SBBTester.send_sub_to_sbb(sbb2, tx_batch_env2, handler_key=0)
    #
    #     self.run_async(sbb1.loop, 2)
    #     self.run_async(sbb2.loop, 2)
    #
    #     # now send him a make next blk
    #     make_next_block = MakeNextBlock.create()
    #     SBBTester.send_ipc_to_sbb(sbb1, make_next_block)
    #     SBBTester.send_ipc_to_sbb(sbb2, make_next_block)
    #
    #     self.run_async(sbb1.loop, 2)
    #     self.run_async(sbb2.loop, 2)
    #
    #     # make sure he called _created_sbc as a result of inputing a bag
    #     sbb1._create_sbc_from_batch.assert_called_once()
    #     sbb2._create_sbc_from_batch.assert_called_once()
    #
    #     self.run_async(sbb1.loop, 2)
    #     self.run_async(sbb2.loop, 2)
    #
    #     # # yet ANOTHER ONE
    #     # make_next_block = MakeNextBlock.create()
    #     # SBBTester.send_ipc_to_sbb(sbb1, make_next_block)
    #     # SBBTester.send_ipc_to_sbb(sbb2, make_next_block)
    #
    #     # THE SECOND
    #     tx_batch_env1 = SBBTester.create_tx_batch_env(10, MN_SK1)
    #     SBBTester.send_sub_to_sbb(sbb1, tx_batch_env1, handler_key=0)
    #
    #
    #     self.run_async(sbb1.loop, 2)
    #     self.run_async(sbb2.loop, 2)
    #     self.assertEqual(sbb1._create_sbc_from_batch.call_count, 2)
    #     self.assertEqual(sbb2._create_sbc_from_batch.call_count, 2)
    #
    # @SBBTester.test
    # # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 2)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    # @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    # def test_execute_hella_bags_two_builder(self, *args):
    #     num_bags = 2
    #     bags_for_1 = []
    #     bags_for_2 = []
    #
    #     for _ in range(num_bags):
    #         tx_batch_env1 = SBBTester.create_tx_batch_env(10, MN_SK1)
    #         tx_batch_env2 = SBBTester.create_tx_batch_env(10, MN_SK1)
    #         bags_for_1.append(tx_batch_env1)
    #         bags_for_2.append(tx_batch_env2)
    #
    #     sbb1 = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
    #     sbb1._create_sbc_from_batch = MagicMock()
    #
    #     sbb2 = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
    #     sbb2._create_sbc_from_batch = MagicMock()
    #
    #     # send intital make next blk notif
    #     make_next_block = MakeNextBlock.create()
    #     SBBTester.send_ipc_to_sbb(sbb1, make_next_block)
    #     SBBTester.send_ipc_to_sbb(sbb2, make_next_block)
    #
    #     # dump all bags on them
    #     for i in range(num_bags):
    #         SBBTester.send_sub_to_sbb(sbb1, bags_for_1[i], handler_key=0)
    #         SBBTester.send_sub_to_sbb(sbb2, bags_for_2[i], handler_key=0)
    #         self.run_async(sbb1.loop, 0.5)
    #         self.run_async(sbb2.loop, 0.5)
    #
    #     self.run_async(sbb1.loop, 1)
    #     self.run_async(sbb2.loop, 1)
    #
    #     # give them the merge calls
    #     for i in range(num_bags):
    #         make_next_block = MakeNextBlock.create()
    #         SBBTester.send_ipc_to_sbb(sbb1, make_next_block)
    #         SBBTester.send_ipc_to_sbb(sbb2, make_next_block)
    #         self.run_async(sbb1.loop, 0.5)
    #         self.run_async(sbb2.loop, 0.5)
    #
    #     self.run_async(sbb1.loop, 1)
    #     self.run_async(sbb2.loop, 1)
    #
    #     self.assertEqual(sbb1._create_sbc_from_batch.call_count, num_bags)
    #     self.assertEqual(sbb2._create_sbc_from_batch.call_count, num_bags)

    @SBBTester.test
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro_ee.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    def test_blk_notification_handler(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        self.assertEqual(len(sbb.sb_managers), 1)
        sbb._send_msg_over_ipc = MagicMock()
        sbb._create_empty_sbc = MagicMock()
        sbb._create_sbc_from_batch = MagicMock()

        # send it 6 blocks w/ 4 txns each except second block (index = 1) is empty
        ib_hashes = []
        for i in range(6):
            num_txs = 0 if i == 1 else 4
            tx_batch = SBBTester.create_tx_batch_env(num_txs=num_txs, env_signing_key=MN_SK1)
            input_hash = Hasher.hash(tx_batch)
            ib_hashes.append(input_hash)
            print("rpc 1:{} {}".format(i, input_hash))
            SBBTester.send_sub_to_sbb(sbb, envelope=tx_batch, handler_key=0)

        # Now, send a MakeNextBlock notif. This should trigger an empty subblock to be built and sent over IPC to BM
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        self.run_async(sbb.loop, 2)
        # should receive a _new subblock for input 0 and assert its input_hash is same as the one above
        # SBBTester.send_ipc_to_sbb(sbb, make_next_block)
        sbb._create_sbc_from_batch.assert_called_once()
        sb = sbb._create_sbc_from_batch.call_args[0][0]
        self.assertEqual(sb.input_hash, ib_hashes[0])

        SBBTester.send_ipc_to_sbb(sbb, make_next_block)
        self.run_async(sbb.loop, 2)
        # should receive a _new subblock for input 1
        sbb._create_empty_sbc.assert_called()
        sb = sbb._create_empty_sbc.call_args[0][0]
        self.assertEqual(sb.input_hash, ib_hashes[1])

        # send align notification for input hash # 3
        # message = AlignInputHash.create(ib_hashes[3], 0)
        # message = AlignInputHash.create(ib_hashes[3], sb_index=0)
        # SBBTester.send_ipc_to_sbb(sbb, message)
        # SBBTester.send_ipc_to_sbb(sbb, make_next_block)
        # self.run_async(sbb.loop, 2)
        # should receive a _new subblock for input 4
        # sbb._create_sbc_from_batch.assert_called()
        # sb = sbb._create_sbc_from_batch.call_args[0][0]
        # self.assertEqual(sb.input_hash, ib_hashes[4])

        # send failedblk notification w/ input hashes 3, 4 
        fih = []
        fih.append(ib_hashes[3])
        fih.append(ib_hashes[4])
        ffih = []
        ffih.append(fih)
        message = FailedBlockNotification.create(ib_hashes[4], ffih)
        SBBTester.send_ipc_to_sbb(sbb, message)
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)
        self.run_async(sbb.loop, 2)
        # should receive a _new subblock for input 5
        sbb._create_sbc_from_batch.assert_called()
        sb = sbb._create_sbc_from_batch.call_args[0][0]
        self.assertEqual(sb.input_hash, ib_hashes[5])


if __name__ == "__main__":
    import unittest
    unittest.main()

from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')
#
from cilantro.logger.base import get_logger
from cilantro.constants.system_config import *
from cilantro.utils.utils import int_to_bytes, bytes_to_int
from cilantro.utils.hasher import Hasher
#
from seneca.engine.conflict_resolution import CRContext
#
from cilantro.nodes.delegate.block_manager import IPC_IP, IPC_PORT
from cilantro.nodes.delegate.sub_block_builder import SubBlockBuilder, SubBlockManager
#
from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.batch import TransactionBatch, build_test_transaction_batch
from cilantro.messages.consensus.sub_block_contender import SubBlockContender, SubBlockContenderBuilder
from cilantro.messages.transaction.data import TransactionData, TransactionDataBuilder
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.messages.signals.delegate import MakeNextBlock
#
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock
#
from cilantro.messages.envelope.envelope import Envelope
import time
#
#
_log = get_logger("TestSubBlockBuilder")
#
TEST_IP = '127.0.0.1'
DELEGATE_SK = TESTNET_DELEGATES[0]['sk']
#
MN_SK1 = TESTNET_MASTERNODES[0]['sk']
MN_SK2 = TESTNET_MASTERNODES[1]['sk']
#
#
class SBBTester:
#
    @staticmethod
    def test(func):
        @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
        @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
        @mock.patch("cilantro.nodes.delegate.block_manager.asyncio", autospec=True)
        @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder.run", autospec=True)
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
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 8)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 8)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    def test_create_sub_sockets(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)

        self.assertEquals(len(sbb.sb_managers), 8)

    @SBBTester.test
    def test_create_empty_sbc(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        input_hash = 'A' * 64
        sbb_idx = 0
        cr_context = CRContext(sbb.client.available_dbs[0], sbb.client.master_db, sbb_idx)
        cr_context.input_hash = input_hash
        sbb._send_msg_over_ipc = MagicMock()

        sbb._create_empty_sbc(cr_context)
        sbb._send_msg_over_ipc.assert_called()
        empty_sbc = sbb._send_msg_over_ipc.call_args[0][0]
        self.assertTrue(isinstance(empty_sbc, SubBlockContender))
        self.assertEqual(empty_sbc.input_hash, input_hash)
        self.assertEqual(empty_sbc.sb_index, sbb_idx)
        self.assertTrue(empty_sbc.is_empty)


    @SBBTester.test
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    def test_one_sb_recv_empty_tx_bag(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        self.assertEquals(len(sbb.sb_managers), 1)

        # Send an empty TX batch. This should get queued up as the SBB doesnt have a MakeNextBlock msg yet
        empty_tx_batch_env = SBBTester.create_tx_batch_env(num_txs=0, env_signing_key=MN_SK1)
        SBBTester.send_sub_to_sbb(sbb, envelope=empty_tx_batch_env, handler_key=0)
        self.assertEqual(len(sbb.sb_managers[0].pending_txs), 1)

        # Now, send a MakeNextBlock notif. This should trigger an empty subblock to be built and sent over IPC to BM
        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

    @SBBTester.test
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    def test_sub_msg_with_make_next_block_notification_calls_handle_ipc_msg(self, *args):
        """
        Tests handle_ipc_msg correctly calls handle_new_block when a NewBlockNotification is received
        """

        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        sbb._send_msg_over_ipc = MagicMock()

        self.assertTrue(len(sbb.sb_managers) == 1)

        # Mock Envelope.from_bytes to return a mock envelope of our choosing
        tx_batch_env = SBBTester.create_tx_batch_env(num_txs=4, env_signing_key=MN_SK1)
        print("print tsns")
        print(tx_batch_env.message.transactions[0])
        SBBTester.send_sub_to_sbb(sbb, envelope=tx_batch_env, handler_key=0)
        

        sbb._make_next_sub_block()

#        time.sleep(2)
#        sbb._send_msg_over_ipc.assert_called_once()
#        msg = sbb._send_msg_over_ipc.call_args[0][0]
#        self.assertTrue(isinstance(msg, SubBlockContender))
#        self.assertTrue(msg.is_empty)
#
    @SBBTester.test
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    def test_handle_new_block_signal_calls_make_next_sub_block(self, *args):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=DELEGATE_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT)
        sbb._make_next_sub_block = MagicMock()

        make_next_block = MakeNextBlock.create()
        SBBTester.send_ipc_to_sbb(sbb, make_next_block)

        sbb._make_next_sub_block.assert_called_once()

    @SBBTester.test
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
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
        self.assertEqual(sbb.sb_managers[0].pending_txs.popleft(), tx_batch.message)

    @SBBTester.test
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
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
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SUB_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_BLOCKS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_BUILDERS", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.NUM_SB_PER_BLOCK_PER_BUILDER", 1)
    @mock.patch("cilantro.nodes.delegate.sub_block_builder.TRANSACTIONS_PER_SUB_BLOCK", 4)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
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
        sbb._send_msg_over_ipc = MagicMock()

        mock_cr_ctx = MagicMock()
        mock_cr_ctx.get_subblock_rep.return_value = sb_rep
        mock_cr_ctx.input_hash = input_hash
        mock_cr_ctx.sbb_idx = sbb_idx

        sbb._create_sbc_from_batch(mock_cr_ctx)

        # TODO assert tis was called with the expected SBC passed in
        sbb._send_msg_over_ipc.assert_called()


if __name__ == "__main__":
    import unittest
    unittest.main()

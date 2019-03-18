from cilantro_ee.logger.base import get_logger
from seneca.engine.interpreter.executor import Executor
from cilantro_ee.messages.transaction.contract import ContractTransaction
from cilantro_ee.messages.transaction.publish import PublishTransaction
from cilantro_ee.messages.block_data.block_data import GENESIS_BLOCK_HASH, BlockData
from cilantro_ee.utils.utils import is_valid_hex
from cilantro_ee.storage.ledis import SafeLedis
from cilantro_ee.constants.system_config import *
from typing import List


class StateDriver:

    BLOCK_HASH_KEY = '_current_block_hash'
    BLOCK_NUM_KEY = '_current_block_num'
    log = get_logger("StateDriver")
    interface = None

    @classmethod
    def update_with_block(cls, block: BlockData):
        # Update state by running Redis outputs from the block's transactions
        publish_txs = []
        for tx in block.transactions:
            assert tx.contract_type is ContractTransaction, "Expected contract tx but got {}".format(tx.contract_type)
            cmds = tx.state.split(';')
            # cls.log.notice('tx has state {}'.format(cmds))
            for cmd in cmds:
                if cmd: SafeLedis.execute_command(*cmd.split(' '))

        # Update our block hash and block num
        cls.set_latest_block_info(block.block_hash, block.block_num)

        if block.block_num % DUMP_TO_CACHE_EVERY_N_BLOCKS == 0:
            try: SafeLedis.bgsave()
            except: pass

        assert cls.get_latest_block_hash() == block.block_hash, "StateUpdate failed! Latest block hash {} does not " \
                                                                "match block data {}".format(cls.get_latest_block_hash(), block)

    @classmethod
    def set_latest_block_info(cls, block_hash: str, block_num: int):
        cls.set_latest_block_hash(block_hash)
        cls.set_latest_block_num(block_num)

    @classmethod
    def get_latest_block_info(cls) -> tuple:
        return cls.get_latest_block_hash(), cls.get_latest_block_num()

    @classmethod
    def get_latest_block_hash(cls) -> str:
        """ Returns the latest block hash from the Redis database """
        b_hash = SafeLedis.get(cls.BLOCK_HASH_KEY)
        return b_hash.decode() if b_hash else GENESIS_BLOCK_HASH

    @classmethod
    def set_latest_block_hash(cls, block_hash: str):
        """ Sets the latest block hash on the Redis database"""
        assert is_valid_hex(block_hash, 64), "block hash {} not valid 64 char hex".format(block_hash)
        SafeLedis.set(cls.BLOCK_HASH_KEY, block_hash)

    @classmethod
    def get_latest_block_num(cls) -> int:
        """ Returns the latest block num from the Redis database """
        b_num = SafeLedis.get(cls.BLOCK_NUM_KEY)
        return int(b_num.decode()) if b_num else 0

    @classmethod
    def set_latest_block_num(cls, block_num: int):
        """ Sets the latest block num on the Redis database"""
        assert block_num >= 0, "block num must be GTE 0"
        SafeLedis.set(cls.BLOCK_NUM_KEY, block_num)

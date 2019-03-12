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
        pipe = SafeLedis.pipeline()
        for tx in block.transactions:
            if tx.contract_type is ContractTransaction:
                cmds = tx.state.split(';')
                for cmd in cmds:
                    if cmd: pipe.execute_command(cmd)
            elif tx.contract_type is PublishTransaction:
                publish_txs.append(tx.transaction)
            else:
                raise Exception('A transaction must be ContractTransaction or PublishTransaction not {}'
                                .format(tx.contract_type))

        if publish_txs:
            cls._process_publish_txs(publish_txs)
        pipe.execute()

        # Update our block hash and block num
        cls.set_latest_block_info(block.block_hash, block.block_num)

        if block.block_num % DUMP_TO_CACHE_EVERY_N_BLOCKS == 0:
            try: SafeLedis.bgsave()
            except: pass

        assert cls.get_latest_block_hash() == block.block_hash, "StateUpdate failed! Latest block hash {} does not " \
                                                                "match block data {}".format(cls.get_latest_block_hash(), block)

    @classmethod
    def _process_publish_txs(cls, txs: List[PublishTransaction]):
        if cls.interface is None:
            cls.interface = Executor()
        for tx in txs:
            # TODO i dont think this api call to publish_code_str is right.....
            cls.log.debug("Storing contract named from sender '{}'".format(tx.contract_name, tx.sender))
            cls.interface.publish_code_str(fullname=tx.contract_name, author=tx.sender, code_str=tx.contract_code)

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

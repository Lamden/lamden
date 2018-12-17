from cilantro.logger.base import get_logger
from seneca.engine.interface import SenecaInterface
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.publish import PublishTransaction
from cilantro.messages.block_data.block_data import GENESIS_BLOCK_HASH, BlockData
from cilantro.utils.utils import is_valid_hex
from cilantro.storage.redis import SafeRedis
from typing import List


class StateDriver:

    BLOCK_HASH_KEY = '_current_block_hash'
    BLOCK_NUM_KEY = '_current_block_num'
    log = get_logger("StateDriver")

    @classmethod
    def update_with_block(cls, block: BlockData):
        # Update state by running Redis outputs from the block's transactions
        publish_txs = []
        pipe = SafeRedis.pipeline()
        for tx in block.transactions:
            if tx.contract_type is ContractTransaction:
                cmds = tx.state.split(';')
                for cmd in cmds:
                    if cmd: pipe.execute_command(cmd)
            elif tx.contract_type is PublishTransaction:
                publish_txs.append(tx)
            else:
                raise Exception('A transaction must be ContractTransaction or PublishTransaction not {}'
                                .format(tx.contract_type))

        if publish_txs:
            cls._process_publish_txs(publish_txs)
        pipe.execute()

        # Update our block hash and block num
        cls.set_latest_block_info(block.block_hash, block.block_num)

    @classmethod
    def _process_publish_txs(cls, txs: List[PublishTransaction]):
        with SenecaInterface(False) as interface:
            for tx in txs:
                cls.log.debug("Storing contract named '{}' from sender '{}'".format(tx.contract_name, tx.sender))
                interface.publish_code_str(fullname=tx.contract_name, author=tx.sender, code_str=tx.contract_code)

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
        b_hash = SafeRedis.get(cls.BLOCK_HASH_KEY)
        return b_hash.decode() if b_hash else GENESIS_BLOCK_HASH

    @classmethod
    def set_latest_block_hash(cls, block_hash: str):
        """ Sets the latest block hash on the Redis database"""
        assert is_valid_hex(block_hash, 64), "block hash {} not valid 64 char hex".format(block_hash)
        SafeRedis.set(cls.BLOCK_HASH_KEY, block_hash)

    @classmethod
    def get_latest_block_num(cls) -> int:
        """ Returns the latest block num from the Redis database """
        b_num = SafeRedis.get(cls.BLOCK_NUM_KEY)
        return int(b_num.decode()) if b_num else 0

    @classmethod
    def set_latest_block_num(cls, block_num: int):
        """ Sets the latest block num on the Redis database"""
        assert block_num >= 0, "block num must be GTE 0"
        SafeRedis.set(cls.BLOCK_NUM_KEY, block_num)



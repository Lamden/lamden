from cilantro.logger.base import get_logger
import redis
from seneca.constants.config import *
from seneca.engine.interface import SenecaInterface
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.publish import PublishTransaction
from cilantro.messages.block_data.block_data import GENESIS_BLOCK_HASH
from cilantro.utils.utils import is_valid_hex
from typing import List


class StateDriver:
    
    BLOCK_HASH_KEY = '_current_block_hash'
    r = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())
    log = get_logger("StateDriver")

    @classmethod
    def update_with_block(cls, block):
        publish_txs = []
        pipe = cls.r.pipeline()
        for tx in block.transactions:
            if tx.contract_type is ContractTransaction:
                cmds = tx.state.split(';')
                for cmd in cmds:
                    if cmd: pipe.execute_command(cmd)
            elif tx.contract_type is PublishTransaction:
                publish_txs.append(tx)
            else:
                raise Exception('A transaction must be ContractTransaction or PublishTransaction')

        if publish_txs:
            cls._process_publish_txs(publish_txs)
        pipe.execute()

    @classmethod
    def _process_publish_txs(cls, txs: List[PublishTransaction]):
        with SenecaInterface(False) as interface:
            for tx in txs:
                cls.log.debug("Storing contract named '{}' from sender '{}'".format(tx.contract_name, tx.sender))
                interface.publish_code_str(fullname=tx.contract_name, author=tx.sender, code_str=tx.contract_code)

    @classmethod
    def get_latest_block_hash(cls) -> str:
        """ Returns the latest block from the Redis database """
        b_hash = cls.r.get(cls.BLOCK_HASH_KEY)
        return b_hash.decode() if b_hash else GENESIS_BLOCK_HASH

    @classmethod
    def set_latest_block_hash(cls, block_hash: str):
        """ Sets the latest block hash on the Redis database"""
        assert is_valid_hex(block_hash, 64), "block hash {} not valid 64 char hex".format(block_hash)
        cls.r.set(cls.BLOCK_HASH_KEY, block_hash)

    

import redis
from seneca.constants.config import *
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.publish import PublishTransaction
from cilantro.messages.block_data.block_data import GENESIS_BLOCK_HASH
from cilantro.utils.utils import is_valid_hex


class StateDriver:

    BLOCK_HASH_KEY = '_current_block_hash'
    r = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())

    @classmethod
    def update_with_block(cls, block):
        pipe = cls.r.pipeline()
        for tx in block.transactions:
            if tx.contract_type is ContractTransaction:
                cmds = tx.state.split(';')
                for cmd in cmds:
                    pipe.execute_command(cmd)
            elif tx.contract_type is PublishTransaction:
                pass # No need to update state
            else:
                raise Exception('A transaction must be ContractTransaction or PublishTransaction')
        pipe.execute()

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

    

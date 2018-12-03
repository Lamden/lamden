import redis
from seneca.constants.config import *
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.publish import PublishTransaction

class StateDriver:

    r = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())

    @classmethod
    def update_with_block(cls, block):
        pipe = cls.r.pipeline()
        for tx in block.transactions:
            if tx.contract_type is ContractTransaction:
                cmds = tx.state.split(';')
                for cmd in cmds:
                    if cmd.strip() == '':
                        continue
                    pipe.execute_command(cmd)
            elif tx.contract_type is PublishTransaction:
                pass # No need to update state
            else:
                raise Exception('A transaction must be ContractTransaction or PublishTransaction')
        pipe.execute()

import redis
from seneca.constants.config import *

class StateDriver:

    r = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())

    @classmethod
    def update_with_block(cls, block):
        pipe = cls.r.pipeline()
        for tx in block.transactions:
            cmds = tx.state.split(';')
            for cmd in cmds:
                pipe.execute_command(cmd)
        pipe.execute()

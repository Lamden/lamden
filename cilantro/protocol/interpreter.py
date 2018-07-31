from cilantro.storage.contracts import run_contract
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.logger import get_logger
from collections import deque
from seneca.seneca_internal.storage.mysql_spits_executer import Executer
from cilantro.constants.protocol import max_queue_delay_ms
from cilantro.storage.tables import DB_NAME
from cilantro.storage.db import DB
from typing import List
from heapq import heappush, heappop
import time, asyncio

class SenecaInterpreter:

    def __init__(self):
        self.log = get_logger(self.__class__.__name__)
        self.queue = deque()
        self.heap = []

        self.max_delay_ms = max_queue_delay_ms
        self.ex = Executer('root', '', DB_NAME, '127.0.0.1')

        # Grab a reference to contracts table from DB singleton
        with DB() as db:
            self.contracts_table = db.tables.contracts

        self.loop = asyncio.get_event_loop()
        self.start()

        # Ensure contracts table was seeded properly
        assert self.contracts_table.select().run(self.ex), "Expected contracts table to be seeded with at least one row"

    def flush(self, update_state=True):
        """
        Flushes internal queue of transactions. If update_state is True, this will also commit the changes
        to the database. Otherwise, this method will discard any changes
        """
        if update_state:
            self.log.info("Flushing queue and committing queue of {} items".format(len(self.queue)))
            self.ex.commit()
        else:
            self.log.info("Flushing queue and rolling back {} transactions".format(len(self.queue)))
            self.ex.rollback()

        self.queue.clear()

    def interpret(self, contract, async=False):
        assert isinstance(contract, OrderingContainer), \
            "Seneca Interpreter can only interpret use_contracts transactions"
        if async:
            time_hash = '%11x' % (contract.utc_time)
            contract_hash = '{}{}'.format(time_hash, contract.masternode_vk)
            heappush(self.heap, (contract_hash, contract))
        else:
            self._run_contract(contract.transaction)

    async def check_contract(self):
        self.log.debug('Checking for runnable contracts...')
        while True:
            try:
                while len(self.heap) > 0:
                    timestamp = int(self.heap[0][0][:11], 16) # 11 is the number of digits representing the time, 16 is the base for hex
                    if timestamp + self.max_delay_ms < time.time()*1000:
                        self._run_contract(self.heap[0][1].transaction)
                        heappop(self.heap)
                    else:
                        break
                await asyncio.sleep(0.05)
            except:
                break

    def _rerun_contracts(self):
        self.ex.rollback()
        for c in self.queue:
            r = self._run_contract(c, rerun=True)
            if not r:
                raise Exception("Previously successul contract {} failed during recovery with code: {}".format(c.sender, c.code))
        if len(self.queue) > 0:
            self.log.debug("Recovered to code with sender {}".format(self.queue[-1].sender))
        else:
            self.log.debug("Restoring to beginning of block")

    def _run_contract(self, contract: ContractTransaction, rerun: bool = False):
        self.log.debug("Executing use_contracts from user {}".format(contract.sender))
        res = run_contract(self.ex, self.contracts_table, contract_id=None, user_id=contract.sender, code_str=contract.code)
        if not res:
            self.log.error("Error executing use_contracts from user {} with code:\n{}".format(contract.sender, contract.code))
            self._rerun_contracts()
        else:
            self.log.debug("Successfully executing use_contracts from sender {}".format(contract.sender))
            if rerun: return res
            else: self.queue.append(contract)

    @property
    def queue_binary(self) -> List[bytes]:
        return [contract.serialize() for contract in self.queue]

    @property
    def queue_size(self):
        return len(self.queue)

    def start(self):
        # Check to see if there are valid contracts to be run
        self.check_contract_future = asyncio.ensure_future(self.check_contract())

    def stop(self):
        self.check_contract_future.cancel()

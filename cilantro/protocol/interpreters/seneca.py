from cilantro.protocol.interpreters.base import BaseInterpreter
from cilantro.db.contracts import run_contract
from cilantro.messages import ContractTransaction
from cilantro.messages.transaction.ordering import OrderingContainer
from seneca.seneca_internal.storage.mysql_spits_executer import Executer
from cilantro.db.tables import DB_NAME
from cilantro.db import DB
from typing import List
from heapq import heappush, heappop
import time, asyncio

class SenecaInterpreter(BaseInterpreter):

    def __init__(self, loop=None):
        super().__init__()

        self.max_delay_ms = 1000
        self.ex = Executer('root', '', DB_NAME, '127.0.0.1')

        # Grab a reference to contracts table from DB singleton
        with DB() as db:
            self.contracts_table = db.tables.contracts

        # Check to see if there are valid contracts to be run
        if not loop: loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)
        self.check_contract_future = asyncio.ensure_future(self.check_contract())

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
            while len(self.heap) > 0:
                timestamp = int(self.heap[0][0][:11], 16) # 11 is the number of digits representing the time, 16 is the base for hex
                if timestamp + self.max_delay_ms < time.time()*1000:
                    self._run_contract(self.heap[0][1].transaction)
                    heappop(self.heap)
                else:
                    break
            await asyncio.sleep(0.05)

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

    def tearDown(self):
        self.check_contract_future.cancel()

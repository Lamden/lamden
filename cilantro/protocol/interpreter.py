from cilantro.logger import get_logger

from cilantro.storage.contracts import run_contract
from cilantro.storage.db import DB

from cilantro.constants.protocol import MAX_QUEUE_DELAY_MS
from cilantro.constants.db import DB_SETTINGS
from cilantro.constants.system_config import MOCK_INTERPRET_TIME

from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.block_data.block_data import TransactionData

from seneca.engine.storage.mysql_spits_executer import Executer

from collections import deque
from heapq import heappush, heappop
from typing import List
import time
import asyncio


class SenecaInterpreter:

    def __init__(self, mock=False):
        self.log = get_logger(self.__class__.__name__)
        self.queue = deque()
        self.heap = []
        self.mock = mock

        self.max_delay_ms = MAX_QUEUE_DELAY_MS

        # Grab a reference to contracts table from DB singleton
        if not mock:
            self.ex = Executer(**DB_SETTINGS)
            with DB() as db:
                self.contracts_table = db.tables.contracts

            self.loop = asyncio.get_event_loop()
            self.check_contract_future = None
            self.start()

            # Ensure contracts table was seeded properly
            assert self.contracts_table.select().run(self.ex), "Expected contracts table to be seeded with at least one row"
        else:
            self.log.notice("Mock Interpreter enabled, with a fixed contract run time of {}".format(MOCK_INTERPRET_TIME))

    def flush(self, update_state=True):
        """
        Flushes internal queue of transactions. If update_state is True, this will also commit the changes
        to the database. Otherwise, this method will discard any changes
        """
        if not self.mock:
            if update_state:
                self.log.info("Flushing queue and committing queue of {} items".format(len(self.queue)))
                self.ex.commit()
            else:
                self.log.info("Flushing queue and rolling back {} transactions".format(len(self.queue)))
                self.ex.rollback()

        self.queue.clear()

    def interpret(self, contract, async=False):
        assert isinstance(contract, OrderingContainer), \
            "Seneca Interpreter can only interpret OrderingContainer instances"
        assert isinstance(contract.transaction, ContractTransaction), "OrderingContainer {} has a non " \
                                                                      "ContractTransaction payload".format(contract)

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
        for data in self.queue:
            c = data.contract_tx
            r = self._run_contract(c, rerun=True)
            if not r:
                raise Exception("Previously successful contract {} failed during recovery with code: {}".format(c.sender, c.code))
        if len(self.queue) > 0:
            self.log.debug("Recovered to code with sender {}".format(self.queue[-1].contract_tx.sender))
        else:
            self.log.debug("Restoring to beginning of block")

    def _run_contract(self, contract: ContractTransaction, rerun: bool = False):
        self.log.spam("Executing use_contracts from user {}. Mock mode enabled: {}".format(contract.sender, self.mock))

        if self.mock:
            time.sleep(MOCK_INTERPRET_TIME)
            self.queue.append(TransactionData.create(contract_tx=contract, status='SUCCESS', state='over9000'))
            return

        res = run_contract(self.ex, self.contracts_table, contract_id=None, user_id=contract.sender, code_str=contract.code)
        if not res:
            self.log.error("Error executing use_contracts from user {} with code:\n{}\nres:{}".format(contract.sender, contract.code, res))
            self._rerun_contracts()
        else:
            self.log.spam("Successfully executing use_contracts from sender {}".format(contract.sender))
            # TODO get 'status' and 'state' from res
            if rerun:
                return res
            else:
                self.queue.append(TransactionData.create(contract_tx=contract, status='SUCCESS', state='over9000'))

    def get_tx_queue(self) -> List[TransactionData]:
        return list(self.queue)

    @property
    def queue_size(self):
        return len(self.queue)

    def start(self):
        assert self.check_contract_future is None, "Start should not be called twice without a .stop() in between!"

        # Check to see if there are valid contracts to be run
        self.check_contract_future = asyncio.ensure_future(self.check_contract())

    def stop(self):
        self.check_contract_future.cancel()
        self.check_contract_future = None

from cilantro.db.contracts import run_contract
from cilantro.messages import ContractTransaction
from seneca.seneca_internal.storage.mysql_spits_executer import Executer
from cilantro.db.tables import DB_NAME
from cilantro.db import DB
from typing import List


class SenecaInterpreter:

    def __init__(self):
        super().__init__()

        self.ex = Executer('root', '', DB_NAME, '127.0.0.1')

        # Grab a reference to contracts table from DB singleton
        with DB() as db:
            self.contracts_table = db.tables.contracts

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

    def interpret(self, contract: ContractTransaction):
        assert isinstance(contract, ContractTransaction), "Seneca Interpreter can only interpret use_contracts transactions"
        res = self._run_contract(contract)
        if not res:
            self.log.error("Error executing use_contracts from user {} with code:\n{}".format(contract.sender, contract.code))
            self._rerun_contracts()
        else:
            self.log.debug("Successfully executing use_contracts from sender {}".format(contract.sender))
            self.queue.append(contract)

    def _rerun_contracts(self):
        self.ex.rollback()
        for c in self.queue:
            r = self._run_contract(c)
            if not r:
                raise Exception("Previously successul contract {} failed during recovery with code: {}".format(contract.sender, contract.code))
        if len(self.queue) > 0:
            self.log.debug("Recovered to code with sender {}".format(self.queue[-1].sender))
        else:
            self.log.debug("Restoring to beginning of block")

    def _run_contract(self, contract: ContractTransaction):
        self.log.debug("Executing use_contracts from user {}".format(contract.sender))
        res = run_contract(self.ex, self.contracts_table, contract_id=None, user_id=contract.sender, code_str=contract.code)
        return res

    @property
    def queue_binary(self) -> List[bytes]:
        return [contract.serialize() for contract in self.queue]

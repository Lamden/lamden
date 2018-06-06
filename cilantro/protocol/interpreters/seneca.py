from cilantro.protocol.interpreters.base import BaseInterpreter
from cilantro.db import *
from cilantro.messages import *

import datetime

import seneca.seneca_internal.storage.easy_db as t
from seneca.seneca_internal.storage.mysql_executer import Executer


class SenecaInterpreter(BaseInterpreter):

    def __init__(self, reset_db=True):
        super().__init__()

        self.ex = Executer.init_local_noauth_dev()
        self.tables = build_tables(self.ex, should_drop=reset_db)

    def flush(self, update_state=True):
        """
        Flushes internal queue and resets scratch. If update_state is True, then this also interprets its transactions
        against state
        """
        raise NotImplementedError

    def interpret(self, obj):
        if isinstance(obj, ContractSubmission):
            self._interpret_submission(obj)
        else:
            self._interpret_contract(obj)

    def _interpret_submission(self, submission: ContractSubmission):
        self.log.debug("Interpreting contract submission: {}".format(submission))

        res = self.contract_table.insert([{
            'contract_id': submission.contract_id,
            'code_str': submission.contract_code,
            'author': submission.user_id,
            'execution_datetime': None,
            'execution_status': 'pending',
        }]).run(self.ex)

        self.log.debug("res: {}".format(res))

    def get_contract_code(self, contract_id):
        q = self.tables.contracts.select(self.tables.contracts.code_str).where(self.contract_table.contract_id == contract_id).run(self.ex)
        print("got q:\n {}".format(q))

    def _interpret_contract(self, contract_id: str):
        raise NotImplementedError

    @property
    def queue_binary(self):
        raise NotImplementedError
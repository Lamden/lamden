from cilantro.protocol.interpreters.base import BaseInterpreter
from cilantro.db import *
from cilantro.messages import *

import datetime

import seneca.seneca_internal.storage.easy_db as t
from seneca.seneca_internal.storage.mysql_executer import Executer


def build_contract_table(ex):
    contract_table = t.Table('smart_contracts',
                    t.Column('contract_id', t.str_len(64), True),
                    [
                        t.Column('code_str', str),
                        t.Column('author', t.str_len(60)),
                        t.Column('execution_datetime', datetime.datetime),
                        t.Column('execution_status', t.str_len(30)),
                    ])

    try:
        contract_table.drop_table().run(ex)
    except Exception as e:
        if e.args[0]['error_code'] == 1051:
            pass
        else:
            raise

    contract_table.create_table().run(ex)

    return contract_table


class SenecaInterpreter(BaseInterpreter):

    def __init__(self):
        super().__init__()

        self.ex = Executer.init_local_noauth_dev()
        self.contract_table = build_contract_table(self.ex)

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
        q = self.contract_table.select(self.contract_table.code_str).where(self.contract_table.contract_id == contract_id).run(self.ex)
        print("got q:\n {}".format(q))

    def _interpret_contract(self, contract_id: str):
        raise NotImplementedError

    @property
    def queue_binary(self):
        raise NotImplementedError
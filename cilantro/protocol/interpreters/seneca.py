from cilantro.protocol.interpreters.base import BaseInterpreter
from cilantro.db import *
from cilantro.messages import *


class SenecaInterpreter(BaseInterpreter):

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
        pass

    def _interpret_contract(self, contract):
        raise NotImplementedError

    @property
    def queue_binary(self):
        raise NotImplementedError
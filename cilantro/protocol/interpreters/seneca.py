from cilantro.protocol.interpreters.base import BaseInterpreter

class SenecaInterpreter(BaseInterpreter):

    def flush(self, update_state=True):
        """
        Flushes internal queue and resets scratch. If update_state is True, then this also interprets its transactions
        against state
        """
        raise NotImplementedError

    def interpret(self, obj):
        raise NotImplementedError

    @property
    def queue_binary(self):
        raise NotImplementedError
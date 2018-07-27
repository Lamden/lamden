from collections import deque
from cilantro.protocol.interpreters.queries import *


class BaseInterpreter:

    def __init__(self):
        self.log = get_logger(self.__class__.__name__)
        self.queue = deque()

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

    @property
    def queue_size(self):
        return len(self.queue)

from cilantro.messages import TransactionBase
from cilantro.logger import get_logger
from collections import deque
from cilantro.db import ScratchCloningVisitor, DB
from sqlalchemy.sql import Update
from cilantro.protocol.interpreters.queries import *
import itertools


class BaseInterpreter:

    def __init__(self):
        self.log = get_logger(self.__class__.__name__)
        self.queue = deque()
        self.heap = []

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

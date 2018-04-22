import asyncio
import functools
from unittest.mock import MagicMock, call, patch
from cilantro.protocol.reactor import NetworkReactor
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from unittest import TestCase
from cilantro.logger import get_logger


URL = 'tcp://127.0.0.1:9988'
FILTER = b'TEST_FILTER'

class TestParent: pass


# def start_sub():
#     parent = TestParent()
#     loop = asyncio.new_event_loop()
#     reactor = NetworkReactor(parent, loop)




if __name__ == '__main__':
    log = get_logger("Main")
    log.debug("hello test")
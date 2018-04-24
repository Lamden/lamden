import asyncio
import zmq.asyncio
from unittest.mock import MagicMock, call, patch
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.core import CHILD_RDY_SIG
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from unittest import TestCase


def AsyncMock(*args, **kwargs):
    m = MagicMock(*args, **kwargs)

    async def mock_coro(*args, **kwargs):
        return m(*args, **kwargs)

    mock_coro.mock = m
    return mock_coro


class IntegrationTestReactor(TestCase):

    def test_subpub_1(self):
        """
        Tests sub/pub 1-1 with one message
        """
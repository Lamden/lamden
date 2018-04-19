import asyncio
import functools
from unittest.mock import MagicMock, call, patch
from cilantro.protocol.reactor import NetworkReactor
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from unittest import TestCase


URL = 'test-url'
FILTER = 'test-filter'


class MockParent(MagicMock): pass


class NonblockingTester:

    def __init__(self, loop):
        self.loop = loop
        self.parent = MockParent()
        self.reactor = None

    def start(self):
        self.reactor = NetworkReactor(parent=self.parent, loop=self.loop)


class TestNetworkReactor(TestCase):

    # def test_child_ready(self):
    #     def fail(loop, test_obj, future):
    #         print("FAILING!!!")
    #         print("stopping future")
    #         loop.call_soon_threadsafe(future.cancel)
    #         loop.call_soon_threadsafe(loop.close)
    #         # future.cancel()
    #         print("did this block....")
    #         # print("closing loop {}".format(loop))
    #         # loop.close()
    #         # print("is htis loop closed? {}".format(loop))
    #         test_obj.assertTrue(False)
    #
    #     loop = asyncio.new_event_loop()
    #     r = NonblockingTester(loop)
    #
    #     fn = functools.partial(r.start)
    #     future = loop.run_in_executor(None, fn)
    #
    #     #loop.call_later(1, fail, loop, self, future)
    #     #loop.call_soon_threadsafe(fail, loop, self, future)
    #
    #     print("about to run start in executor")
    #
    #
    #     print("hey did this block???")
    #
    #     self.assertTrue(True)
    #
    #     print("ok im here")

    async def _mock_wait_child_rdy(self):
        print("mock waiting child ready...")
        await asyncio.sleep(1)
        print("child ready")

    # @patch('')
    def test_add_sub(self):
        cls_name = SubPubExecutor.__name__
        cls_func = SubPubExecutor.add_sub.__name__
        cmd = ReactorCommand.create(cls_name, cls_func, url=URL, filter=FILTER)
        cmd_binary = cmd.serialize()

        parent = MockParent()
        loop = asyncio.new_event_loop()
        reactor = NetworkReactor(parent=parent, loop=loop)

        reactor.socket.send = MagicMock()

        reactor.add_sub(url=URL, filter=FILTER)
        reactor.socket.send.assert_called_with(cmd_binary)

        loop.close()
        reactor.proc.terminate()

    def test_remove_sub(self):
        cls_name = SubPubExecutor.__name__
        cls_func = SubPubExecutor.remove_pub.__name__
        cmd = ReactorCommand.create(cls_name, cls_func, url=URL, filter=FILTER)
        cmd_binary = cmd.serialize()

        parent = MockParent()
        loop = asyncio.new_event_loop()
        reactor = NetworkReactor(parent=parent, loop=loop)

        reactor.socket.send = MagicMock()

        reactor.remove_sub(url=URL, filter=FILTER)
        reactor.socket.send.assert_called_with(cmd_binary)






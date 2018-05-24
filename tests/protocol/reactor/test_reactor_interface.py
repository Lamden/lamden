# import asyncio
# import zmq.asyncio
# from unittest.mock import MagicMock, call, patch
# from cilantro.protocol.reactor import ReactorInterface
# from cilantro.protocol.reactor.core import CHILD_RDY_SIG
# from cilantro.protocol.reactor.executor import *
# from cilantro.messages import ReactorCommand
# from unittest import TestCase
#
#
# def AsyncMock(*args, **kwargs):
#     m = MagicMock(*args, **kwargs)
#
#     async def mock_coro(*args, **kwargs):
#         return m(*args, **kwargs)
#
#     mock_coro.mock = m
#     return mock_coro
#
#
# class TestReactorInterface(TestCase):
#
#     @patch('cilantro.protocol.reactor.interface.LProcess')
#     @patch('zmq.asyncio.Context')
#     @patch('cilantro.protocol.reactor.interface.asyncio')
#     def test_init_set_loop_router(self, async_mock: MagicMock, ctx: MagicMock, lproc: MagicMock):
#         """
#         Tests that the init function sets the event loop and router
#         """
#         loop = MagicMock()
#         router = MagicMock()
#
#         reactor = ReactorInterface(router, loop)
#
#         self.assertTrue(reactor.router is router)
#         async_mock.set_event_loop.assert_called_with(loop)
#
#     @patch('cilantro.protocol.reactor.interface.LProcess')
#     @patch('zmq.asyncio.Context')
#     @patch('cilantro.protocol.reactor.interface.asyncio')
#     def test_init_create_context_socket(self, async_mock: MagicMock, ctx: MagicMock, lproc: MagicMock):
#         """
#         Tests that init creates a context and a ZMQ Pair socket
#         """
#         loop = MagicMock()
#         router = MagicMock()
#
#         ctx_obj = MagicMock()
#         ctx.return_value = ctx_obj
#         socket = MagicMock()
#         ctx_obj.socket.return_value = socket
#
#         reactor = ReactorInterface(router, loop)
#
#         ctx.assert_called()
#         ctx_obj.socket.assert_called_with(zmq.PAIR)
#         socket.bind.assert_called()
#
#     @patch('cilantro.protocol.reactor.interface.LProcess')
#     @patch('zmq.asyncio.Context')
#     @patch('cilantro.protocol.reactor.interface.asyncio')
#     def test_init_start_proc(self, async_mock: MagicMock, ctx: MagicMock, lproc: MagicMock):
#         """
#         Tests that init creates a context and a ZMQ Pair socket
#         """
#         print("\n[inside test case] lproc is: {}\n".format(lproc))
#
#         loop = MagicMock()
#         router = MagicMock()
#
#         proc = MagicMock()
#         lproc.return_value = proc
#
#         reactor = ReactorInterface(router, loop)
#
#         lproc.assert_called()
#         proc.start.assert_called()
#
#     @patch('cilantro.protocol.reactor.interface.LProcess')
#     @patch('zmq.asyncio.Context')
#     @patch('cilantro.protocol.reactor.interface.asyncio')
#     def test_init_loop_start(self, async_mock: MagicMock, ctx: MagicMock, lproc: MagicMock):
#         """
#         Tests that init runs _wait_child_rdy() until complete, and then run ensure_future on self._recv_messages()
#         """
#         loop = MagicMock()
#         router = MagicMock()
#
#         reactor = ReactorInterface(router, loop)
#
#         loop.run_until_complete.assert_called()
#         async_mock.ensure_future.assert_called()
#
#     @patch('cilantro.protocol.reactor.interface.LProcess')
#     @patch('zmq.asyncio.Context')
#     @patch('cilantro.protocol.reactor.interface.asyncio')
#     def test_wait_child_rdy(self, async_mock: MagicMock, ctx: MagicMock, lproc: MagicMock):
#         """
#         Tests that receiving the correct message from the child proc unblocks the init process
#         """
#         loop = asyncio.new_event_loop()
#         router = MagicMock()
#
#         ctx_obj = MagicMock()
#         ctx.return_value = ctx_obj
#         socket = MagicMock()
#         socket.recv = AsyncMock(return_value=CHILD_RDY_SIG)
#         ctx_obj.socket.return_value = socket
#
#         reactor = ReactorInterface(router, loop)
#
#         async_mock.ensure_future.assert_called()
#
#     @patch('cilantro.protocol.reactor.interface.LProcess')
#     @patch('zmq.asyncio.Context')
#     @patch('cilantro.protocol.reactor.interface.asyncio')
#     def test_wait_child_rdy_invalid(self, async_mock: MagicMock, ctx: MagicMock, lproc: MagicMock):
#         """
#         Tests that receiving an incorrect ready signal from the child proc throws an assertion
#         """
#         wrong_rdy_sig = b'XD'
#
#         loop = asyncio.new_event_loop()
#         router = MagicMock()
#
#         ctx_obj = MagicMock()
#         ctx.return_value = ctx_obj
#         socket = MagicMock()
#         socket.recv = AsyncMock(return_value=wrong_rdy_sig)
#         ctx_obj.socket.return_value = socket
#
#         self.assertRaises(Exception, ReactorInterface, router, loop)
#
#     # TODO -- build and test start/stop signals on ReactorInterface

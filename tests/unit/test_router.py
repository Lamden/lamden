from unittest import TestCase

from lamden import router, authentication

from lamden.crypto.wallet import Wallet
import zmq.asyncio
import asyncio
from contracting.db.encoder import encode, decode
from contracting.client import ContractingClient


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestRouter(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_add_service(self):
        r = router.Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)
        q = router.QueueProcessor()

        r.add_service('test', q)

        self.assertEqual(r.services['test'], q)

    def test_inbox_none_returns_default_message(self):
        r = router.Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        bad_message = {
            'blah': 123
        }

        tasks = asyncio.gather(
            r.serve(),
            request(bad_message),
            stop_server(r, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], router.OK)

    def test_request_none_returns_default_message(self):
        r = router.Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        bad_message = {
            'service': 'hello',
            'blah': 123
        }

        tasks = asyncio.gather(
            r.serve(),
            request(bad_message),
            stop_server(r, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], router.OK)

    def test_no_processor_returns_default_message(self):
        r = router.Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        bad_message = {
            'service': 'hello',
            'msg': {
                'hello': 123
            }
        }

        tasks = asyncio.gather(
            r.serve(),
            request(bad_message),
            stop_server(r, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], router.OK)

    def test_queue_processor_returns_default_message(self):
        r = router.Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)
        q = router.QueueProcessor()

        r.add_service('test', q)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        message = {
            'service': 'test',
            'msg': {
                'howdy': 'there'
            }
        }

        expected_q = [{
                'howdy': 'there'
            }]

        tasks = asyncio.gather(
            r.serve(),
            request(message),
            stop_server(r, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], router.OK)
        self.assertListEqual(expected_q, q.q)

    def test_mock_processor_returns_custom_message(self):
        r = router.Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        class MockProcessor(router.Processor):
            async def process_message(self, msg):
                return {
                    'whats': 'good'
                }

        q = MockProcessor()

        r.add_service('test', q)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        message = {
            'service': 'test',
            'msg': {
                'howdy': 'there'
            }
        }

        expected_msg = {
                    'whats': 'good'
                }

        tasks = asyncio.gather(
            r.serve(),
            request(message),
            stop_server(r, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertDictEqual(res[1], expected_msg)


class TestAsyncServer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        w = Wallet()
        router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx)

    def test_sockets_are_initially_none(self):
        w = Wallet()
        m = router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx)

        self.assertIsNone(m.socket)

    def test_setup_frontend_creates_socket(self):
        w = Wallet()
        m = router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx)
        m.setup_socket()

        self.assertEqual(m.socket.type, zmq.ROUTER)
        self.assertEqual(m.socket.getsockopt(zmq.LINGER), m.linger)

    def test_sending_message_returns_it(self):
        w = Wallet()
        m = router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx, linger=500, poll_timeout=500)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10000')

            await socket.send(msg)

            res = await socket.recv()

            return res

        tasks = asyncio.gather(
            m.serve(),
            get(b'howdy'),
            stop_server(m, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], b'howdy')


class TestJSONAsyncInbox(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        router.JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx)

    def test_sockets_are_initially_none(self):
        m = router.JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx)

        self.assertIsNone(m.socket)

    def test_setup_frontend_creates_socket(self):
        m = router.JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx)
        m.setup_socket()

        self.assertEqual(m.socket.type, zmq.ROUTER)
        self.assertEqual(m.socket.getsockopt(zmq.LINGER), m.linger)

    def test_sending_message_returns_it(self):
        m = router.JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx, linger=2000, poll_timeout=50)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10000')

            await socket.send(msg)

            res = await socket.recv()

            return res

        tasks = asyncio.gather(
            m.serve(),
            get(b'{"howdy":"abc"}'),
            stop_server(m, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], b'{"howdy":"abc"}')

    def test_secure_request_sends_as_service(self):
        authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

        w = Wallet()
        w2 = Wallet()

        authenticator.add_verifying_key(w.verifying_key)
        authenticator.add_verifying_key(w2.verifying_key)
        authenticator.configure()

        m = router.JSONAsyncInbox(
            socket_id='tcp://127.0.0.1:10000',
            ctx=self.ctx,
            linger=2000,
            poll_timeout=50,
            secure=True,
            wallet=w
        )

        async def get():
            r = await router.secure_request(
                msg={'hello': 'there'},
                service='something',
                wallet=w2,
                vk=w.verifying_key,
                ip='tcp://127.0.0.1:10000',
                ctx=self.ctx
            )

            return r

        tasks = asyncio.gather(
            m.serve(),
            get(),
            stop_server(m, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertDictEqual(res[1], {'service': 'something', 'msg': {'hello': 'there'}})

    def test_secure_request_returns_result(self):
        authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

        w = Wallet()
        w2 = Wallet()

        authenticator.add_verifying_key(w.verifying_key)
        authenticator.add_verifying_key(w2.verifying_key)
        authenticator.configure()

        class MockProcessor(router.Processor):
            async def process_message(self, msg):
                return {
                    'whats': 'good'
                }

        m = router.Router(
            socket_id='tcp://127.0.0.1:10000',
            ctx=self.ctx,
            linger=2000,
            poll_timeout=50,
            secure=True,
            wallet=w
        )

        m.add_service('something', MockProcessor())

        async def get():
            r = await router.secure_request(
                msg={'hello': 'there'},
                service='something',
                wallet=w2,
                vk=w.verifying_key,
                ip='tcp://127.0.0.1:10000',
                ctx=self.ctx
            )

            return r

        tasks = asyncio.gather(
            m.serve(),
            get(),
            stop_server(m, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        print(res[1])

        self.assertDictEqual(res[1], {'whats': 'good'})

        authenticator.authenticator.stop()

    def test_secure_request_cannot_connect_returns_none(self):
        authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

        w = Wallet()
        w2 = Wallet()

        authenticator.add_verifying_key(w.verifying_key)
        authenticator.add_verifying_key(w2.verifying_key)
        authenticator.configure()

        async def get():
            r = await router.secure_request(
                msg={'hello': 'there'},
                service='something',
                wallet=w2,
                vk=w.verifying_key,
                ip='tcp://x',
                ctx=self.ctx
            )

            return r

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(get())

        self.assertEqual(res, None)

        authenticator.authenticator.stop()

    def test_secure_sec_cannot_connect_returns_none(self):
        authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

        w = Wallet()
        w2 = Wallet()

        authenticator.add_verifying_key(w.verifying_key)
        authenticator.add_verifying_key(w2.verifying_key)
        authenticator.configure()

        async def get():
            r = await router.secure_send(
                msg={'hello': 'there'},
                service='something',
                wallet=w2,
                vk=w.verifying_key,
                ip='tcp://x',
                ctx=self.ctx
            )

            return r

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(get())

        self.assertEqual(res, None)

        authenticator.authenticator.stop()

    def test_secure_send_receives_messages(self):
        authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

        w = Wallet()
        w2 = Wallet()

        authenticator.add_verifying_key(w.verifying_key)
        authenticator.add_verifying_key(w2.verifying_key)
        authenticator.configure()

        m = router.Router(
            socket_id='tcp://127.0.0.1:10000',
            ctx=self.ctx,
            linger=2000,
            poll_timeout=50,
            secure=True,
            wallet=w
        )

        q = router.QueueProcessor()
        m.add_service('something', q)

        async def get():
            await router.secure_send(
                msg={'hello': 'there'},
                service='something',
                wallet=w2,
                vk=w.verifying_key,
                ip='tcp://127.0.0.1:10000',
                ctx=self.ctx
            )

        tasks = asyncio.gather(
            m.serve(),
            get(),
            stop_server(m, 1),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertEqual(q.q[0], {'hello': 'there'})

        authenticator.authenticator.stop()

    def test_multicast_sends_to_multiple(self):
        authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

        w1 = Wallet()
        w2 = Wallet()
        w3 = Wallet()

        authenticator.add_verifying_key(w1.verifying_key)
        authenticator.add_verifying_key(w2.verifying_key)
        authenticator.add_verifying_key(w3.verifying_key)
        authenticator.configure()

        m1 = router.Router(
            socket_id='tcp://127.0.0.1:10000',
            ctx=self.ctx,
            linger=2000,
            poll_timeout=50,
            secure=True,
            wallet=w1
        )

        q1 = router.QueueProcessor()
        m1.add_service('something', q1)

        m2 = router.Router(
            socket_id='tcp://127.0.0.1:10001',
            ctx=self.ctx,
            linger=2000,
            poll_timeout=50,
            secure=True,
            wallet=w2
        )

        q2 = router.QueueProcessor()
        m2.add_service('something', q2)

        async def get():
            peers = {
                w1.verifying_key: 'tcp://127.0.0.1:10000',
                w2.verifying_key: 'tcp://127.0.0.1:10001'
            }

            await router.secure_multicast(
                msg={'hello': 'there'},
                service='something',
                wallet=w3,
                peer_map=peers,
                ctx=self.ctx
            )

        tasks = asyncio.gather(
            m1.serve(),
            m2.serve(),
            get(),
            stop_server(m1, 1),
            stop_server(m2, 1),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertEqual(q1.q[0], {'hello': 'there'})
        self.assertEqual(q2.q[0], {'hello': 'there'})

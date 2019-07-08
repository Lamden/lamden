from unittest import TestCase
from cilantro_ee.protocol.comm.services import SubscriptionService
import zmq.asyncio
import asyncio


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestSubscriptionService(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        SubscriptionService(ctx=self.ctx)

    def test_add_subscription_modifies_dict(self):
        s = SubscriptionService(ctx=self.ctx)

        s.add_subscription('tcp://127.0.0.1:10001')
        s.add_subscription('tcp://127.0.0.1:10002')
        s.add_subscription('tcp://127.0.0.1:10003')
        s.add_subscription('tcp://127.0.0.1:10004')

        self.assertTrue(s.subscriptions['tcp://127.0.0.1:10001'])
        self.assertTrue(s.subscriptions['tcp://127.0.0.1:10002'])
        self.assertTrue(s.subscriptions['tcp://127.0.0.1:10003'])
        self.assertTrue(s.subscriptions['tcp://127.0.0.1:10004'])

    def test_remove_subscription_deletes_from_dict(self):
        s = SubscriptionService(ctx=self.ctx)

        s.add_subscription('tcp://127.0.0.1:10001')
        s.add_subscription('tcp://127.0.0.1:10002')
        s.add_subscription('tcp://127.0.0.1:10003')
        s.add_subscription('tcp://127.0.0.1:10004')

        s.remove_subscription('tcp://127.0.0.1:10001')
        s.remove_subscription('tcp://127.0.0.1:10003')

        self.assertIsNone(s.subscriptions.get('tcp://127.0.0.1:10001'))
        self.assertTrue(s.subscriptions['tcp://127.0.0.1:10002'])
        self.assertIsNone(s.subscriptions.get('tcp://127.0.0.1:10003'))
        self.assertTrue(s.subscriptions['tcp://127.0.0.1:10004'])

    def test_pub_sub_single_socket(self):
        pub = self.ctx.socket(zmq.PUB)
        pub.bind('inproc://test1')

        s = SubscriptionService(ctx=self.ctx)

        s.add_subscription('inproc://test1')

        tasks = asyncio.gather(
            s.serve(),
            pub.send(b'howdy'),
            pub.send(b'howdy2'),
            stop_server(s, 0.1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertListEqual(s.received, [(b'howdy', 'inproc://test1'), (b'howdy2', 'inproc://test1')])

    def test_pub_sub_multi_sockets(self):
        pub1 = self.ctx.socket(zmq.PUB)
        pub1.bind('inproc://test1')

        pub2 = self.ctx.socket(zmq.PUB)
        pub2.bind('inproc://test2')

        s = SubscriptionService(ctx=self.ctx)

        s.add_subscription('inproc://test1')
        s.add_subscription('inproc://test2')

        tasks = asyncio.gather(
            s.serve(),
            pub1.send(b'howdy'),
            pub2.send(b'howdy2'),
            stop_server(s, 0.1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertListEqual(s.received, [(b'howdy', 'inproc://test1'), (b'howdy2', 'inproc://test2')])

    def test_pub_sub_multi_sockets_remove_one(self):
        pub1 = self.ctx.socket(zmq.PUB)
        pub1.bind('inproc://test1')

        pub2 = self.ctx.socket(zmq.PUB)
        pub2.bind('inproc://test2')

        s = SubscriptionService(ctx=self.ctx)

        s.add_subscription('inproc://test1')
        s.add_subscription('inproc://test2')

        async def remove():
            s.remove_subscription('inproc://test2')

        async def delayed_send():
            await asyncio.sleep(0.2)
            pub2.send(b'howdy2')

        tasks = asyncio.gather(
            s.serve(),
            pub1.send(b'howdy'),
            remove(),
            stop_server(s, 0.2),
            delayed_send()
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertListEqual(s.received, [(b'howdy', 'inproc://test1')])
        self.assertListEqual(s.to_remove, [])

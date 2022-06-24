import json

import zmq
import zmq.asyncio
import asyncio
import unittest

class MockSubscriber():
    def __init__(self, callback=None, port=19080, multipart=True, ctx=None):
        self.running = False

        self.ctx = ctx or zmq.asyncio.Context().instance()
        self.socket = None
        self.address = f'tcp://127.0.0.1:{port}'
        self.callback = callback

        self.multipart = multipart

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def start(self):
        self.socket = self.ctx.socket(zmq.SUB)
        self.socket.bind(self.address)
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

        print(f'[SUBSCRIBER] Started on {self.address}.')

        asyncio.ensure_future(self.check_for_messages())

    def subscribe(self, topic):
        self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode('UTF-8'))

    async def has_message(self, timeout=10) -> bool:
        return await self.socket.poll(timeout=timeout, flags=zmq.POLLIN) > 0

    async def check_for_messages(self) -> None:
        self.running = True

        await self.has_message()

        while self.running:
            if await self.has_message(timeout=50):
                print(f'[SUBSCRIBER] Got event from {self.address}. Receiving message...')

                try:
                    if self.multipart:
                        data = await self.socket.recv_multipart()
                    else:
                        data = await self.socket.recv()

                    print(f'[SUBSCRIBER] Message received: {data}')

                    if self.callback:
                        self.callback(data)
                except Exception as err:
                    print(err)

        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()

    async def stopping(self):
        while not self.socket.closed:
            await asyncio.sleep(0)


    def stop(self):
        if self.running:
            self.running = False

            tasks = asyncio.gather(
                self.stopping()
            )
            self.loop.run_until_complete(tasks)

            print(f'[SUBSCRIBER] Stopped...')

class TestMockSubscriber(unittest.TestCase):
    def setUp(self) -> None:
        self.subscriber = None
        self.data = None
        self.ctx = zmq.asyncio.Context().instance()

    def tearDown(self) -> None:
        if self.subscriber:
            self.subscriber.stop()
            del self.subscriber

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def store_data(self, data):
        self.data = data

    def start_subscriber(self, multipart=True):
        self.subscriber = MockSubscriber(callback=self.store_data, multipart=multipart)
        self.subscriber.start()
        self.async_sleep(1)

    def test_can_create_instance__MOCKSUBSCRIBER(self):
        self.start_subscriber()

        self.assertIsInstance(self.subscriber, MockSubscriber)
        self.assertTrue(self.subscriber.running)
        self.assertFalse(self.subscriber.socket.closed)

    def test_can_create_instance__MOCKSUBSCRIBER_stops(self):
        self.start_subscriber()
        self.assertIsNotNone(self.subscriber)
        self.assertTrue(self.subscriber.running)

        try:
            self.subscriber.stop()
        except Exception:
            self.fail("Request did not stop cleanly!")

        self.assertFalse(self.subscriber.running)
        self.assertTrue(self.subscriber.socket.closed)

    def test_can_grab_multipart_messages_from_socket(self):
        ctx = zmq.asyncio.Context().instance()

        pub = ctx.socket(zmq.PUB)
        pub.connect('tcp://127.0.0.1:19080')

        self.start_subscriber()

        # the first sub.poll is a workaround to force subscription propagation
        self.async_sleep(1)

        topic = 'testing'
        message = {'testing': True}

        pub.send_multipart([topic.encode('UTF-8'), json.dumps(message).encode('UTF-8')])

        #self.assertEqual(1, evt)
        self.async_sleep(1)

        self.assertIsNotNone(self.data)
        self.assertEqual(2, len(self.data))
        self.assertEqual(topic, self.data[0].decode('UTF-8'))
        self.assertEqual(message, json.loads(self.data[1]))

    def test_can_grab_string_message_from_socket(self):
        ctx = zmq.asyncio.Context().instance()

        pub = ctx.socket(zmq.PUB)
        pub.connect('tcp://127.0.0.1:19080')

        self.start_subscriber(multipart=False)

        # the first sub.poll is a workaround to force subscription propagation
        self.async_sleep(1)

        message = 'testing'

        pub.send_string(message)

        #self.assertEqual(1, evt)
        self.async_sleep(1)

        self.assertIsNotNone(self.data)
        self.assertIsInstance(self.data, bytes)
        self.assertEqual(message, self.data.decode('UTF-8'))

    def test_can_grab_object_message_from_socket(self):
        ctx = zmq.asyncio.Context().instance()

        pub = ctx.socket(zmq.PUB)
        pub.connect('tcp://127.0.0.1:19080')

        self.start_subscriber(multipart=False)

        # the first sub.poll is a workaround to force subscription propagation
        self.async_sleep(1)

        message = {'testing': True}
        pub.send(json.dumps(message).encode('UTF-8'))

        #self.assertEqual(1, evt)
        self.async_sleep(1)

        self.assertIsNotNone(self.data)
        self.assertIsInstance(self.data, bytes)
        self.assertEqual(message, json.loads(self.data))
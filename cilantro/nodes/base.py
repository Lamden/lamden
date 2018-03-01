"""A pypi demonstration vehicle.

.. moduleauthor:: Foo Bar <foo@bar.com>

"""

from multiprocessing import Process, Queue
import zmq
import asyncio

from cilantro import Constants

from cilantro.logger import get_logger

class ZMQScaffolding:
    def __init__(self, filters=(b'', )):
        self.base_url = Constants.BaseNode.BaseUrl
        self.subscriber_port = Constants.BaseNode.SubscriberPort
        self.publisher_port = Constants.BaseNode.PublisherPort
        self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)
        self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

        self.context = None
        self.sub_socket = None
        self.pub_socket = None

        self.filters = filters
        self.logger = get_logger(name='ZMQScaffolding')

    def connect(self):
        self.context = zmq.Context()

        self.sub_socket = self.context.socket(socket_type=zmq.SUB)
        self.pub_socket = self.context.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.publisher_url)

        self.logger.info("ZMQ is binding")
        self.sub_socket.bind(self.subscriber_url)

        for f in self.filters:
            self.sub_socket.subscribe(f)


class ConveyorBelt:
    def __init__(self, callback):
        self.callback = callback

    async def loop(self, **kwargs):
        raise NotImplementedError


class ZMQConveyorBelt(ConveyorBelt):
    async def loop(self, sub_socket=None):
        while True:
            msg = await sub_socket.recv()
            self.callback(msg)


class LocalConveyorBelt(ConveyorBelt):
    async def loop(self, queue=None):
        while True:
            msg = queue.get()
            self.callback(msg)


class BaseNode:
    def __init__(self, start=True, **kwargs):
        """

        :param start:
        :param kwargs:
        """
        self.queue = Queue()
        self.serializer = Constants.Protocol.Serialization
        self.process = Process(target=self.run)

        self.message_queue = ZMQScaffolding(**kwargs)

        self.zmq_conveyor_belt = ZMQConveyorBelt(callback=self.zmq_recv_callback)
        self.mpq_conveyor_belt = LocalConveyorBelt(callback=self.mpq_recv_callback)

        self.conveyor_belts = [self.zmq_conveyor_belt, self.mpq_conveyor_belt]

        self.logger = get_logger('BaseNode')

        if start:
            self.process.start()

    def run(self):
        """

        :return:
        """
        self.logger.info('Running async event loop.')
        self.message_queue.connect()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.wait([c.loop() for c in self.conveyor_belts]))

    def zmq_recv_callback(self, msg):
        raise NotImplementedError

    def mpq_recv_callback(self, msg):
        raise NotImplementedError

    def terminate(self):
        """

        :return:
        """
        self.process.terminate()

    def mp_eval(self, eval_statement):
        self.queue.put(('EVAL', eval_statement))

if __name__ == '__main__':
    import time
    b = BaseNode()
    time.sleep(2)
    b.terminate()
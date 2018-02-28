from unittest import TestCase
from cilantro.nodes import BaseNode, ZMQScaffolding, ZMQConveyorBelt, LocalConveyorBelt

from cilantro import Constants
from multiprocessing import Queue, Process


class TestBaseNode(TestCase):
    def test_setup(self):
        b = BaseNode()
        b.terminate()

    def test_prestart_vars(self):
        b = BaseNode(start=False)
        self.assertTrue(b.serializer == Constants.Protocol.Serialization)
        self.assertTrue(b.queue.__class__ == Queue().__class__)
        self.assertTrue(b.message_queue.__class__ == ZMQScaffolding)
        self.assertTrue(b.zmq_conveyor_belt.__class__ == ZMQConveyorBelt)
        self.assertTrue(b.mpq_conveyor_belt.__class__ == LocalConveyorBelt)
        self.assertTrue(b.process.__class__ == Process)
        self.assertTrue(b.conveyor_belts == [b.zmq_conveyor_belt, b.mpq_conveyor_belt])

        self.assertTrue(b.message_queue.base_url == Constants.BaseNode.BaseUrl)
        self.assertTrue(b.message_queue.subscriber_port == Constants.BaseNode.SubscriberPort)
        self.assertTrue(b.message_queue.publisher_port == Constants.BaseNode.PublisherPort)
        self.assertTrue(b.message_queue.subscriber_url == 'tcp://{}:{}'.format(b.message_queue.base_url,
                                                                               b.message_queue.subscriber_port))
        self.assertTrue(b.message_queue.publisher_url == 'tcp://{}:{}'.format(b.message_queue.base_url,
                                                                              b.message_queue.publisher_port))

        self.assertTrue(b.message_queue.context is None)
        self.assertTrue(b.message_queue.sub_socket is None)
        self.assertTrue(b.message_queue.pub_socket is None)

        self.assertTrue(b.message_queue.filters == (b'', ))
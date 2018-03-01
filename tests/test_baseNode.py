from unittest import TestCase
from cilantro.nodes import BaseNode, ZMQScaffolding, ZMQConveyorBelt, LocalConveyorBelt

from cilantro import Constants
from multiprocessing import Queue, Process
import zmq
from time import sleep


class TestBaseNode(TestCase):
    def test_setup(self):
        b = BaseNode()
        b.terminate()

    def test_prestart_vars(self):
        b = BaseNode(start=False)
        self.assertTrue(b.serializer == Constants.Protocol.Serialization)
        self.assertTrue(b.mpq_queue.__class__ == Queue().__class__)
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

    def test_basic_local_queue(self):
        class MockNode(BaseNode):
            def zmq_recv_callback(self, msg):
                pass

            def mpq_recv_callback(self, msg):
                self.main_queue.put(msg)

        m = MockNode()
        m.mpq_queue.put('hello world!')
        mm = m.main_queue.get()
        m.terminate()
        print(mm)
        self.assertEqual(mm, 'hello world!')

    def test_basic_zmq_queue(self):
        class Publisher(BaseNode):
            def zmq_recv_callback(self, msg):
                pass

            def mpq_recv_callback(self, msg: str):
                print('recieved', msg)
                self.message_queue.pub_socket.send(msg.encode())
                print('published')

        class Subscriber(BaseNode):
            def zmq_recv_callback(self, msg: str):
                print('callback issued')
                self.main_queue.put(msg)

            def mpq_recv_callback(self, msg):
                pass

        m = Publisher(subscriber_port=9791,
                      publisher_port=9777)
        sleep(1)

        m2 = Subscriber(subscriber_port=9777,
                        publisher_port=9799)
        sleep(1)

        print('put this')
        m.mpq_queue.put('hello world!')

        sleep(1)
        mm = m2.main_queue.get()
        #self.assertFalse(m2.main_queue.empty())
        m.terminate()
        m2.terminate()


        print(mm)
        self.assertEqual(mm, 'hello world!'.encode())

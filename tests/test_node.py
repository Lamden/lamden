from unittest import TestCase
from cilantro.nodes import Node
from aioprocessing import AioConnection, AioPipe
from time import sleep
import zmq
import asyncio


class Subscriber(Node):
    def zmq_callback(self, msg):
        print('received message from publisher. putting it on the queue:', msg)
        self.child_pipe.send(msg)
        print('done')

    def pipe_callback(self, msg):
        pass


class Publisher(Node):
    def zmq_callback(self, msg):
        pass

    def pipe_callback(self, msg):
        print('received a message on the queue. publishing it:', msg)
        self.pub_socket.send(msg)


class TestNode(TestCase):
    def test_node_init(self):
        s = Subscriber(sub_port=1234, pub_port=5678)

        self.assertTrue(s.parent_pipe.__class__ == AioConnection)
        self.assertTrue(s.child_pipe.__class__ == AioConnection)

        self.assertTrue(s.subscriber_port == 1234)
        self.assertTrue(s.publisher_port == 5678)

        self.assertTrue(s.base_url == '127.0.0.1')

        self.assertTrue(s.subscriber_url == 'tcp://127.0.0.1:1234')
        self.assertTrue(s.publisher_url == 'tcp://127.0.0.1:5678')

        self.assertTrue(s.context is None)
        self.assertTrue(s.sub_socket is None)
        self.assertTrue(s.pub_socket is None)

    def test_simple_pub_sub(self):
        s = Subscriber()
        s.start()
        sleep(1)

        p = Publisher(pub_port=9999, sub_port=9997)
        p.start()
        sleep(1)

        print('publishing message')
        p.parent_pipe.send(b'hello world')

        sleep(1)
        message = s.parent_pipe.recv()

        p.terminate()
        s.terminate()

        self.assertTrue(message == b'hello world')

    def test_multiprocessing_context(self):
        class Returner(Node):
            def __init__(self):
                super().__init__()
                self.test_pipe_parent, self.test_pipe_child = AioPipe()

            def pipe_callback(self, msg):
                if self.context.__class__ == zmq.Context:
                    self.test_pipe_child.send(b'pass')
                else:
                    self.test_pipe_child.send(b'fail')

            def zmq_callback(self, msg):
                pass

        r = Returner()
        r.start()
        r.parent_pipe.send(b'')
        self.assertTrue(r.test_pipe_parent.recv() == b'pass')
        r.terminate()

    def test_multiprocessing_socket(self):
        class Returner(Node):
            def __init__(self):
                super().__init__()
                self.test_pipe_parent, self.test_pipe_child = AioPipe()

            def pipe_callback(self, msg):
                if self.sub_socket.__class__ == zmq.Socket and self.pub_socket.__class__ == zmq.Socket:
                    self.test_pipe_child.send(b'pass')
                else:
                    self.test_pipe_child.send(b'fail')

            def zmq_callback(self, msg):
                pass

        r = Returner()
        r.start()
        r.parent_pipe.send(b'')
        self.assertTrue(r.test_pipe_parent.recv() == b'pass')
        r.terminate()
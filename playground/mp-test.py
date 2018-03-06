from multiprocessing import Process, Queue, Lock, Pipe
from time import sleep


def test_basic():
    # put something in the queue on one node, pass it to the other, return it to the main thread
    def pickup(queue1, queue2):
        while True:
            msg = queue1.get()
            queue2.put(msg)

    msg = 'object'

    q = Queue()
    qq = Queue()

    p = Process(target=pickup, args=(q, qq, ))
    p.start()

    q.put(msg)
    print(qq.get())
    p.terminate()


def test_basic_zmq():
    import zmq
    from cilantro import Constants

    base_url = Constants.BaseNode.BaseUrl
    subscriber_port = Constants.BaseNode.SubscriberPort
    publisher_port = Constants.BaseNode.PublisherPort

    subscriber_url = 'tcp://{}:{}'.format(base_url, subscriber_port)
    publisher_url = 'tcp://{}:{}'.format(base_url, publisher_port)


    def pickup(queue):
        print('multiprocess started')
        context = zmq.Context()

        sub_socket = context.socket(socket_type=zmq.SUB)

        pub_socket = context.socket(socket_type=zmq.PUB)
        pub_socket.connect(publisher_url)

        sub_socket.bind(subscriber_url)
        sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

        while True:
            print('waiting for message')
            msg = sub_socket.recv()
            queue.put(msg)
            print('put', msg)

    qqq = Queue()

    import time
    time.sleep(1)

    p = Process(target=pickup, args=(qqq, ))
    p.start()

    context = zmq.Context()
    pub_socket = context.socket(socket_type=zmq.PUB)
    pub_socket.connect(subscriber_url)

    time.sleep(1)

    pub_socket.send(b'hello')

    msg = qqq.get()
    print(msg)
    p.terminate()


def test_basic_q_and_zmq():
    import zmq
    from cilantro import Constants

    class Subscriber(Process):
        def __init__(self, queue=None):
            super().__init__()
            self.base_url = Constants.BaseNode.BaseUrl
            self.subscriber_port = Constants.BaseNode.SubscriberPort

            self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

            self.context = None
            self.sub_socket = None

            self.queue = queue

        def run(self, *args):
            super().run()
            self.context = zmq.Context()

            self.sub_socket = self.context.socket(socket_type=zmq.SUB)

            self.sub_socket.bind(self.subscriber_url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

            self.loop()

        def loop(self):
            while True:
                print('subscriber waiting to receive message from zmq')
                message = self.sub_socket.recv()
                self.queue.put(message)
                print('put on local queue:', message)


    class Publisher(Process):
        def __init__(self, queue=None):
            super().__init__()
            self.base_url = Constants.BaseNode.BaseUrl
            self.publisher_port = Constants.BaseNode.SubscriberPort

            self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

            self.context = None
            self.pub_socket = None

            self.queue = queue

        def run(self, *args):
            super().run()
            self.context = zmq.Context()

            self.pub_socket = self.context.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.publisher_url)

            self.loop()

        def loop(self):
            while True:
                print('publisher waiting for message from main thread')
                message = self.queue.get()
                self.pub_socket.send(message)
                print('pub message on zmq:', message)


    q = Queue()
    qq = Queue()
    s = Subscriber(queue=q)
    s.start()

    sleep(1)

    p = Publisher(queue=qq)
    p.start()

    sleep(1)

    qq.put(b'hello!')

    sleep(1)

    print('q is empty...' if q.empty() else 'q is not empty. got: {}'.format(q.get()))

    p.terminate()
    s.terminate()


def test_basic_q_and_zmq_with_non_blocking():
    import zmq
    from cilantro import Constants
    import multiprocessing as mp

    class Node(Process):
        def __init__(self, queue=None, lock=None, sub_port=9999, pub_port=9998):
            super().__init__()
            # assert mp structures are in place
            assert queue is not None and lock is not None, 'Both a queue and a lock must be provided.'
            # establish base url
            self.base_url = Constants.BaseNode.BaseUrl

            # setup subscriber constants
            self.subscriber_port = sub_port
            self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

            # setup publisher constants
            self.publisher_port = pub_port
            self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

            # set context and sockets to none until process starts because multiprocessing zmq is funky
            self.context = None
            self.sub_socket = None
            self.pub_socket = None

            # set queue
            self.queue = queue
            self.lock = lock

        def run(self, *args):
            super().run()
            self.context = zmq.Context()

            self.sub_socket = self.context.socket(socket_type=zmq.SUB)

            self.sub_socket.bind(self.subscriber_url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

            self.pub_socket = self.context.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.publisher_url)

            self.loop()

        def loop(self):
            print('node entering loop where it will non-block check zmq and local queue')
            while True:
                try:
                    self.zmq_callback(self.sub_socket.recv(flags=zmq.NOBLOCK))
                except zmq.Again:
                    pass

                try:
                    with self.lock:
                        self.q_callback(self.queue.get(block=False))
                except:
                    pass

        def zmq_callback(self, msg):
            raise NotImplementedError

        def q_callback(self, msg):
            raise NotImplementedError

    class Subscriber(Node):
        def zmq_callback(self, msg):
            print('received message from publisher. putting it on the queue:', msg)
            self.queue.put(msg)
            print('done')

        def q_callback(self, msg):
            pass

    class Publisher(Node):
        def zmq_callback(self, msg):
            pass

        def q_callback(self, msg):
            print('received a message on the queue. publishing it:', msg)
            self.pub_socket.send(msg)
    lock = Lock()

    sq = Queue()
    s = Subscriber(queue=sq, lock=lock)
    s.start()
    sleep(1)

    pq = Queue()
    p = Publisher(queue=pq, lock=lock, pub_port=9999, sub_port=9997)
    p.start()
    sleep(1)

    pq.put(b'hello world')
    sleep(1)
    print('q is empty...' if sq.empty() else 'q is not empty. got: {}'.format(sq.get()))

    p.terminate()
    s.terminate()


def test_basic_q_and_zmq_with_threads():
    import zmq
    from cilantro import Constants
    from threading import Thread

    class Node(Thread):
        def __init__(self, queue=None, sub_port=9999, pub_port=9998):
            super().__init__()
            # assert mp structures are in place

            # establish base url
            self.base_url = Constants.BaseNode.BaseUrl

            # setup subscriber constants
            self.subscriber_port = sub_port
            self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

            # setup publisher constants
            self.publisher_port = pub_port
            self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

            # set context and sockets to none until process starts because multiprocessing zmq is funky
            self.context = None
            self.sub_socket = None
            self.pub_socket = None

            # set queue
            self.queue = queue

        def run(self, *args):
            super().run()
            self.context = zmq.Context()

            self.sub_socket = self.context.socket(socket_type=zmq.SUB)

            self.sub_socket.bind(self.subscriber_url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

            self.pub_socket = self.context.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.publisher_url)

            self.loop()

        def loop(self):
            print('node entering loop where it will non-block check zmq and local queue')
            while True:
                try:
                    self.zmq_callback(self.sub_socket.recv(flags=zmq.NOBLOCK))
                except zmq.Again:
                    pass

                try:
                    self.q_callback(self.queue.pop())
                except:
                    pass

        def zmq_callback(self, msg):
            raise NotImplementedError

        def q_callback(self, msg):
            raise NotImplementedError

    class Subscriber(Node):
        def zmq_callback(self, msg):
            print('received message from publisher. putting it on the queue:', msg)
            self.queue.append(msg)
            print('done')

        def q_callback(self, msg):
            pass

    class Publisher(Node):
        def zmq_callback(self, msg):
            pass

        def q_callback(self, msg):
            print('received a message on the queue. publishing it:', msg)
            print(self.queue)
            self.pub_socket.send(msg)

    sq = []
    s = Subscriber(queue=sq)
    s.start()
    sleep(1)

    pq = []
    p = Publisher(queue=pq, pub_port=9999, sub_port=9997)
    p.start()
    sleep(1)

    pq.append(b'hello world')
    sleep(1)
    print('q is empty...' if len(sq) == 0 else 'q is not empty. got: {}'.format(sq.pop()))

    #p.exit()
    #s.exit()


def test_multiprocessing_array():
    from multiprocessing import Array

    class P(Process):
        def __init__(self, array):
            super().__init__()
            self.array = array

        def modify_array(self, array):
            self.array = array

        def flush_array(self):
            self.array[:] = Array(ctypes.c_byte, 1024)

        def get_from_array(self):
            b = b''
            for x in range(len(self.array)):
                if self.array[x] == 0:
                    break
                b += bytes([self.array[x]])
            return b

        def pop(self):
            x = self.get_from_array()
            self.flush_array()
            return x

    import ctypes
    a = Array(ctypes.c_byte, 1024)
    print(a[0:11])
    a[0:11] = b'hello world'
    p = P(a)

    print(p.array[0:11])

    print(p.get_from_array())

    p.flush_array()

    print(p.array[0:11])


def test_basic_q_and_zmq_with_pipe():
    import zmq
    from cilantro import Constants

    class Node(Process):
        def __init__(self, pipe=None, sub_port=9999, pub_port=9998):
            super().__init__()
            # assert mp structures are in place
            assert pipe is not None, 'A pipe must be provided.'
            # establish base url
            self.base_url = Constants.BaseNode.BaseUrl

            # setup subscriber constants
            self.subscriber_port = sub_port
            self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

            # setup publisher constants
            self.publisher_port = pub_port
            self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

            # set context and sockets to none until process starts because multiprocessing zmq is funky
            self.context = None
            self.sub_socket = None
            self.pub_socket = None

            # set queue
            self.pipe = pipe

        def run(self, *args):
            super().run()
            self.context = zmq.Context()

            self.sub_socket = self.context.socket(socket_type=zmq.SUB)

            self.sub_socket.bind(self.subscriber_url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

            self.pub_socket = self.context.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.publisher_url)

            self.loop()

        def loop(self):
            print('node entering loop where it will non-block check zmq and local queue')
            while True:
                try:
                    self.zmq_callback(self.sub_socket.recv(flags=zmq.NOBLOCK))
                except zmq.Again:
                    pass

                try:
                    if self.pipe.poll():
                        self.q_callback(self.pipe.recv())
                except:
                    pass

        def zmq_callback(self, msg):
            raise NotImplementedError

        def q_callback(self, msg):
            raise NotImplementedError

    class Subscriber(Node):
        def zmq_callback(self, msg):
            print('received message from publisher. putting it on the queue:', msg)
            self.pipe.send(msg)
            print('done')

        def q_callback(self, msg):
            pass

    class Publisher(Node):
        def zmq_callback(self, msg):
            pass

        def q_callback(self, msg):
            print('received a message on the queue. publishing it:', msg)
            self.pub_socket.send(msg)

    s_parent_pipe, s_child_pipe = Pipe()
    s = Subscriber(pipe=s_child_pipe)
    s.start()
    sleep(1)

    p_parent_pipe, p_child_pipe = Pipe()
    p = Publisher(pipe=p_child_pipe, pub_port=9999, sub_port=9997)
    p.start()
    sleep(1)

    p_parent_pipe.send(b'hello world')
    sleep(1)
    print('q is empty...' if not s_parent_pipe.poll() else 'q is not empty. got: {}'.format(s_parent_pipe.recv()))

    p.terminate()
    s.terminate()


def test_basic_q_with_pipe_async():
    import asyncio
    from aioprocessing import AioPipe

    class Node(Process):
        def __init__(self, pipe=None):
            super().__init__()
            # assert mp structures are in place
            assert pipe is not None, 'A pipe must be provided.'

            # set queue
            self.pipe = pipe

        def run(self, *args):
            super().run()

            self.loop()

        def loop(self):
            print('node entering loop where it will non-block check zmq and local queue')
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            tasks = [
                asyncio.async(self.get_from_pipe(self.pipe)),
            ]
            loop.run_until_complete(asyncio.wait(tasks))
            loop.close()

        async def get_from_pipe(self, pipe):
            while True:
                pipe.send(pipe.recv())

    p_parent_pipe, p_child_pipe = AioPipe()
    p = Node(pipe=p_child_pipe)
    p.start()
    sleep(1)

    p_parent_pipe.send(b'hello world')

    sleep(1)
    print('q is empty...' if not p_parent_pipe.poll() else 'q is not empty. got: {}'.format(p_parent_pipe.recv()))

    p.terminate()


def test_basic_q_and_zmq_with_pipe_async():
    import zmq
    from cilantro import Constants
    import asyncio
    from aioprocessing import AioPipe

    class Node(Process):
        def __init__(self, pipe=None, sub_port=9999, pub_port=9998):
            super().__init__()
            # assert mp structures are in place
            assert pipe is not None, 'A pipe must be provided.'

            # establish base url
            self.base_url = Constants.BaseNode.BaseUrl

            # setup subscriber constants
            self.subscriber_port = sub_port
            self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

            # setup publisher constants
            self.publisher_port = pub_port
            self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

            # set context and sockets to none until process starts because multiprocessing zmq is funky
            self.context = None
            self.sub_socket = None
            self.pub_socket = None

            # set pipe
            self.pipe = pipe

        def run(self, *args):
            super().run()

            self.context = zmq.Context()

            self.sub_socket = self.context.socket(socket_type=zmq.SUB)

            self.sub_socket.bind(self.subscriber_url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

            self.pub_socket = self.context.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.publisher_url)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self.listen())

        async def listen(self):
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(None, self.receive_from_pipe, self.pipe),
                loop.run_in_executor(None, self.receive_from_socket, self.sub_socket)
            ]
            await asyncio.wait(tasks)

        def receive_from_socket(self, socket):
            print('zmq')
            while True:
                self.zmq_callback(socket.recv())

        def receive_from_pipe(self, pipe):
            print('pipe')
            while True:
                self.pipe_callback(pipe.recv())

        def zmq_callback(self, msg):
            raise NotImplementedError

        def pipe_callback(self, msg):
            raise NotImplementedError

    class Subscriber(Node):
        def zmq_callback(self, msg):
            print('received message from publisher. putting it on the queue:', msg)
            self.pipe.send(msg)
            print('done')

        def pipe_callback(self, msg):
            pass

    class Publisher(Node):
        def zmq_callback(self, msg):
            pass

        def pipe_callback(self, msg):
            print('received a message on the queue. publishing it:', msg)
            self.pub_socket.send(msg)

    s_parent_pipe, s_child_pipe = AioPipe()
    s = Subscriber(pipe=s_child_pipe)
    s.start()
    sleep(1)

    p_parent_pipe, p_child_pipe = AioPipe()
    p = Publisher(pipe=p_child_pipe, pub_port=9999, sub_port=9997)
    p.start()
    sleep(1)

    print('publishing message')
    p_parent_pipe.send(b'hello world')

    sleep(1)
    print('q is empty...' if not s_parent_pipe.poll() else 'q is not empty. got: {}'.format(s_parent_pipe.recv()))

    p.terminate()
    s.terminate()


def test_abstracted_node():
    import zmq
    from cilantro import Constants
    import asyncio
    from aioprocessing import AioPipe

    class Node(Process):
        def __init__(self, sub_port=9999, pub_port=9998):
            super().__init__()
            self.parent_pipe, self.child_pipe = AioPipe()

            # establish base url
            self.base_url = Constants.BaseNode.BaseUrl

            # setup subscriber constants
            self.subscriber_port = sub_port
            self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

            # setup publisher constants
            self.publisher_port = pub_port
            self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

            # set context and sockets to none until process starts because multiprocessing zmq is funky
            self.context = None
            self.sub_socket = None
            self.pub_socket = None

        def run(self, *args):
            super().run()

            self.context = zmq.Context()

            self.sub_socket = self.context.socket(socket_type=zmq.SUB)

            self.sub_socket.bind(self.subscriber_url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

            self.pub_socket = self.context.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.publisher_url)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self.listen())

        async def listen(self):
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(None, self.receive, self.child_pipe, self.pipe_callback),
                loop.run_in_executor(None, self.receive, self.sub_socket, self.zmq_callback)
            ]
            await asyncio.wait(tasks)

        @staticmethod
        def receive(socket, callback):
            while True:
                callback(socket.recv())

        def zmq_callback(self, msg):
            raise NotImplementedError

        def pipe_callback(self, msg):
            raise NotImplementedError

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

    s = Subscriber()
    s.start()
    sleep(1)

    p = Publisher(pub_port=9999, sub_port=9997)
    p.start()
    sleep(1)

    print('publishing message')
    p.parent_pipe.send(b'hello world')

    sleep(1)
    print('q is empty...' if not s.parent_pipe.poll() else 'q is not empty. got: {}'.format(s.parent_pipe.recv()))

    p.terminate()
    s.terminate()

def test_single_process_node():
    import zmq
    from cilantro import Constants
    import asyncio

    class Node(Process):
        def __init__(self, sub_port=9999, pub_port=9998):
            super().__init__()
            # establish base url
            self.base_url = Constants.BaseNode.BaseUrl

            # setup subscriber constants
            self.subscriber_port = sub_port
            self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

            # setup publisher constants
            self.publisher_port = pub_port
            self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

            # set context and sockets to none until process starts because multiprocessing zmq is funky

            self.context = zmq.Context()

            self.sub_socket = self.context.socket(socket_type=zmq.SUB)

            self.sub_socket.bind(self.subscriber_url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

            self.pub_socket = self.context.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.publisher_url)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self.listen())

        async def listen(self):
            loop = asyncio.get_event_loop()
            print('hm')
            tasks = [
                loop.run_in_executor(None, self.receive, self.sub_socket, self.zmq_callback)
            ]
            await asyncio.wait(tasks)

        @staticmethod
        def receive(socket, callback):
            while True:
                callback(socket.recv())

        def zmq_callback(self, msg):
            raise NotImplementedError


    class Subscriber(Node):
        def zmq_callback(self, msg):
            print('received message from publisher. putting it on the queue:', msg)

    class Publisher(Node):
        def zmq_callback(self, msg):
            pass


    s = Subscriber()
    s.start()
    sleep(1)

    p = Publisher(pub_port=9999, sub_port=9997)
    p.start()
    sleep(1)

    print('publishing message')
    p.pub_socket.send(b'hello world')

    sleep(1)
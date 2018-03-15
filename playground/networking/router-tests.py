from threading import Thread
from cilantro.nodes import Subprocess, BIND, CONNECT
import zmq
import asyncio
from time import sleep

class Router(Thread):
    def __init__(self, callbacks):
        super().__init__()
        self.callbacks = callbacks
        self.daemon = True

    def run(self):
        super().run()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(self.listen())

    async def listen(self):
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, self.receive, c[0], c[1]) for c in self.callbacks]
        await asyncio.wait(tasks)

    @staticmethod
    def receive(socket, callback):
        print("router got callback: {}".format(callback))
        while True:
            callback(socket.recv())


class SPA(Subprocess):
    def __init__(self,
                 name='subscriber',
                 connection_type=BIND,
                 socket_type=zmq.REP,
                 url='inproc://abd'):
        super().__init__(name, connection_type, socket_type, url)

    def pipe_callback(self, msg):
        # self.logger.info('SBA got a message: {}'.format(msg))
        self._pipe.send(msg + b'FROM_SBA')

    def zmq_callback(self, msg):
        pass

class SPB(Subprocess):
    def __init__(self,
                 name='subscriber',
                 connection_type=BIND,
                 socket_type=zmq.REP,
                 url='inproc://abc'):
        super().__init__(name, connection_type, socket_type, url)

    def pipe_callback(self, msg):
        # self.logger.info('SBB got a message: {}'.format(msg))
        self._pipe.send(msg + b'FROM_SBB')

    def zmq_callback(self, msg):
        pass


def foo(msg):
    print('inside foo')
    print(msg)


sp_a = SPA()
sp_b = SPB()

sp_a.start()
sp_b.start()

callbacks = [(sp_a.pipe, foo),
             (sp_b.pipe, foo)]

router = Router(callbacks)
router.start()

print('router and processes started')

sleep(1)

sp_a.pipe.send(b'holla ')
sp_b.pipe.send(b'hella ')

sleep(1)

print('yes?')

sp_a.terminate()
sp_b.terminate()
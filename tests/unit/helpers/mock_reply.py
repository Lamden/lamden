import asyncio
import threading
from lamden.crypto.wallet import Wallet
import zmq

class MockReply(threading.Thread):
    def __init__(self, port=19000):
        threading.Thread.__init__(self)
        self.daemon = True

        self.wallet = Wallet()
        self.port = port

        self.ctx = None
        self.socket = None

        self.poller = zmq.Poller()
        self.poll_time = 0.01

        self.running = False
        self.loop = None

        self.start()

    def setup_socket(self):
        self.ctx = zmq.Context()

        self.socket = self.ctx.socket(zmq.REP)
        self.poller.register(self.socket, zmq.POLLIN)

    def run(self):
        self.setup_socket()
        self.socket.bind(f"tcp://*:{self.port}")
        self.running = True

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.check_for_messages())

    async def check_for_messages(self):
        while self.running:
            sockets = dict(self.poller.poll(self.poll_time))
            # print(sockets[self.socket])
            if self.socket in sockets:
                msg = self.socket.recv()
                print("Received request: ", msg)
                self.send_msg(msg=msg)

            await asyncio.sleep(0)

        try:
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
            self.ctx.term()
        except zmq.ZMQError as err:
            self.log.error(f'[ROUTER] Error Stopping Socket: {err}')
            print(f'[{self.log.name}][ROUTER] Error Stopping Socket: {err}')
            pass

    def send_msg(self, msg):
        self.socket.send(msg)

    def stop(self):
        if self.running:
            self.running = False
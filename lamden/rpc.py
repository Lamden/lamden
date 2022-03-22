import zmq
import zmq.asyncio


class RPCObject:
    def __init__(self, id):
        self.id = id
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)

    def setup_socket(self):
        self.socket.bind(f'ipc://{self.id}')

    async def loop(self):
        while self.is_running:
            self.socket
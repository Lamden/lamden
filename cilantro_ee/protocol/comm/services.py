from cilantro_ee.protocol.wallet import Wallet
import zmq


class RequestReplyService:
    def __init__(self, address: str, wallet: Wallet, ctx: zmq.Context, linger=2000, poll_timeout=2000):
        self.address = address
        self.wallet = wallet
        self.ctx = ctx

        self.socket = None

        self.linger = linger
        self.poll_timeout = poll_timeout

        self.running = False

    async def serve(self):
        self.socket = self.ctx.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.bind(self.address)

        self.running = True

        while self.running:
            event = await self.socket.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
            if event:
                msg = await self.socket.recv()

                result = self.handle_msg(msg)

                await self.socket.send(result)

        self.socket.close()

    def handle_msg(self, msg):
        return msg

    def stop(self):
        self.running = False


class Request:
    def __init__(self, address: str, ctx:zmq.Context, timeout=500, linger=2000):
        self.address = address
        self.ctx = ctx
        self.timeout = timeout
        self.linger = linger

    async def get(self, msg: bytes):
        try:
            socket = self.ctx.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, self.linger)

            socket.connect(self.address)

            await socket.send(msg)

            event = await socket.poll(timeout=self.timeout, flags=zmq.POLLIN)
            if event:
                response = await socket.recv()

                socket.close()

                return response
            else:
                return None
        except Exception as e:
            return None


def generate_router_socket(self, identity, linger=2000, handover=1, mandatory=1):
    router = self.ctx.socket(zmq.ROUTER)

    router.setsockopt(zmq.LINGER, linger)
    router.setsockopt(zmq.ROUTER_HANDOVER, handover)
    router.setsockopt(zmq.ROUTER_MANDATORY, mandatory)

    router.setsockopt(zmq.IDENTITY, self.identity_from_salt(identity))

    return router


async def router_fire(address: str, identity: bytes, ctx:zmq.Context):
    pass


async def get(address: str, msg: bytes, ctx:zmq.Context, timeout=500, linger=2000):
    try:
        socket = ctx.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, linger)

        socket.connect(address)

        await socket.send(msg)

        event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
        if event:
            response = await socket.recv()

            socket.close()

            return response
        else:
            return None
    except Exception as e:
        return None
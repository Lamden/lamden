from cilantro.protocol.comm.lsocket_new import LSocketBase
import zmq, zmq.asyncio, asyncio


class LSocketPub(LSocketBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ready = False


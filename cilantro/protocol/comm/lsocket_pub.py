from cilantro.protocol.comm.lsocket_new import LSocketBase
import zmq, zmq.asyncio, asyncio


class LSocketPub(LSocketBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ready = False  # We default ready to False until we connect/bind

    def _connect_or_bind(self, *args, **kwargs):
        super()._connect_or_bind(*args, **kwargs)

        # Once this PUB socket has connected/binded, we set ready to True
        self.ready = True

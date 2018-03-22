from cilantro.protocol.statemachine import State, recv, recv_req
from cilantro.nodes import NodeBase
from cilantro.messages import Envelope, MessageBase
import time

URL = 'tcp://127.0.0.1:3530'


class PokeRequest(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes): return data.decode()
    def validate(self): pass
    def serialize(self): return self._data.encode()


class PokeReply(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes): return data.decode()
    def validate(self): pass
    def serialize(self): return self._data.encode()


class DavisBootState(State):
    def enter(self, prev_state):
        self.parent.reactor.add_dealer(url=URL, id='DAVIS')

    def run(self):
        self.parent.transition(DavisRunState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()

class DavisRunState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass

    def run(self):
        time.sleep(1)
        count = 0
        while True:
            time.sleep(2)
            self.log.debug("requesting from stu..")
            poke = PokeRequest.from_data("sup mayne {}".format(count))
            self.parent.reactor.request(url=URL, data=Envelope.create(poke).serialize())
            count += 1

    @recv(PokeReply)
    def recv_poke(self, poke: PokeReply):
        self.log.critical("Davis got poke reply {}".format(poke))


class StuBootState(State):
    def enter(self, prev_state):
        self.parent.reactor.add_router(url=URL)

    def run(self):
        self.parent.transition(StuRunState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()


class StuRunState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass

    def run(self): pass

    @recv_req(PokeRequest)
    def reply_poke(self, poke: PokeRequest, id):
        self.log.critical("Stu replying to poke <{}> with id {}".format(poke, id))
        reply = PokeReply.from_data("yoyo this is my reply to {}".format(poke))
        return Envelope.create(reply).serialize()


class Davis(NodeBase):
    _STATES = [DavisBootState, DavisRunState]
    _INIT_STATE = DavisBootState

class Stu(NodeBase):
    _STATES =  [StuBootState, StuRunState]
    _INIT_STATE = StuBootState



if __name__ == "__main__":
    stu = Stu()
    time.sleep(0.5)
    davis = Davis()

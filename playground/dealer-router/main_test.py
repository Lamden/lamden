from cilantro.protocol.statemachine import State, input, input_request, input_timeout
from cilantro.nodes import NodeBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
import time

URL = 'tcp://127.0.0.1:3530'
URL2 = 'tcp://127.0.0.1:6100'

SEND_RATE = 1
NUM_SENDS = 2
TIMEOUT = 3
REPLY_WAIT = 0.5

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

class Stab(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes): return data.decode()
    def validate(self): pass
    def serialize(self): return self._data.encode()

class DavisBootState(State):
    def enter(self, prev_state):
        # self.parent.reactor.add_dealer(url=URL, id='DAVIS')
        self.parent.reactor.add_sub(url=URL2)

    def run(self):
        self.parent.transition(DavisRunState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()

class DavisRunState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass

    def run(self):
        pass
        # time.sleep(1)
        # count = 0
        # while count < NUM_SENDS:
        #     time.sleep(SEND_RATE)
        #     self.log.critical("requesting from stu..")
        #     poke = PokeRequest.from_data("sup {}".format(count))
        #     self.parent.reactor.request(url=URL, data=Envelope.create(poke), timeout=TIMEOUT)
        #     count += 1

    @input(PokeReply)
    def recv_poke(self, poke: PokeReply):
        self.log.critical("*** Davis got poke reply {}".format(poke))

    @input(Stab)
    def recv_stab(self, stab: Stab):
        self.log.critical("!!! got stab: {}".format(stab))

    @input_timeout(PokeRequest)
    def poke_timeout(self, poke_req: PokeRequest):
        self.log.warning("poke request {} timed out!".format(poke_req))


class StuBootState(State):
    def enter(self, prev_state):
        # self.parent.reactor.add_router(url=URL)
        self.parent.reactor.add_pub(url=URL2)

    def run(self):
        self.parent.transition(StuRunState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()


class StuRunState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass

    def run(self):
        count = 0
        while count < NUM_SENDS:
            time.sleep(SEND_RATE)
            self.log.critical("Stu sending stab")
            stab = Stab.from_data("stab #{}".format(count))
            self.parent.reactor.pub(url=URL2, data=Envelope.create(stab))
            count += 1

    @input_request(PokeRequest)
    def recv_poke_req(self, poke: PokeRequest, id):
        self.log.critical("Stu got poke {}, but waiting {} seconds...".format(REPLY_WAIT))
        time.sleep(REPLY_WAIT)
        self.log.critical("Stu replying to poke <{}> with id {}".format(poke, id))
        reply = PokeReply.from_data("yoyo this is my reply to {}".format(poke))

        stab = Stab.from_data("stab!")
        self.parent.reactor.pub(url=URL2, data=Envelope.create(stab))

        return reply


class Davis(NodeBase):
    _STATES = [DavisBootState, DavisRunState]
    _INIT_STATE = DavisBootState

class Stu(NodeBase):
    _STATES =  [StuBootState, StuRunState]
    _INIT_STATE = StuBootState


if __name__ == "__main__":
    davis = Davis()
    time.sleep(0.2)
    stu = Stu()

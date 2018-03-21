"""
Extends upon V1 to support state machine
"""

from cilantro.logger import get_logger
from cilantro.protocol.reactor import NetworkReactor
from cilantro.messages import Envelope, MessageBase
from cilantro.protocol.statemachine import StateMachine, State, EmptyState

URL = "tcp://127.0.0.1:5566"
URL2 = "tcp://127.0.0.1:5577"
URL3 = "tcp://127.0.0.1:5588"
URL4 = "tcp://127.0.0.1:5599"
SUB_URLS = [URL]


class Poke(MessageBase):
    def serialize(self) -> bytes:
        return self._data.encode()

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data.decode()


class SubBootState(State):
    def enter(self, prev_state):
        for sub in SUB_URLS:
            self.log.debug("Adding sub {}".format(sub))
            self.parent.reactor.add_sub(url=sub)
    def exit(self, next_state):
        self.parent.reactor.notify_ready()
    def run(self):
        self.parent.transition(SubRunState)

class SubRunState(State):
    def enter(self, prev_state):
        pass
    def exit(self, next_state):
        pass
    def run(self):
        pass

    @receive(Poke)
    def recv_poke(self, poke: Poke):
        self.log.critical("RUN state poked: {}".format(poke._data))
        self.parent.transition(SubPokedState)
        self.log.critical("did i transtion...?")

class SubPokedState(State):
    def enter(self, prev_state):
        pass
    def exit(self, next_state):
        pass
    def run(self):
        self.log.info("im here cause i was poked :/")

    @receive(Poke)
    def recv_poke(self, poke: Poke):
        self.log.critical("POKED state poked: {}".format(poke._data))
        self.parent.transition(SubRunState)
        # self.log.critical("did i transtion...?")

class NodeMeta(type):

    def __new__(cls, clsname, bases, clsdict):
        print("LogMeta NEW for class {}".format(clsname))
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        clsobj.log = get_logger(clsname)

        clsobj._receivers = {r._recv: r for r in clsdict.values() if hasattr(r, '_recv')}
        print("_receivers: ", clsobj._receivers)

        return clsobj


class NodeBase(StateMachine):

    def __init__(self, url):
        self.url = url
        self.reactor = NetworkReactor(self)
        self.log = get_logger(type(self).__name__)
        super().__init__()

    def route(self, msg_binary: bytes):
        msg = None
        try:
            envelope = Envelope.from_bytes(msg_binary)
            msg = envelope.open()
        except Exception as e:
            self.log.error("Error opening envelope: {}".format(e))

        if type(msg) in self.state._receivers:
            self.log.debug("Routing msg: {}".format(msg))
            self.state._receivers[type(msg)](self.state, msg)
        else:
            self.log.error("Message {} has no implemented receiver for state {} in receivers {}"
                           .format(msg, self.state, self.state._receivers))


class SubNode(NodeBase):
    _STATES = [SubBootState, SubRunState, SubPokedState]
    _INIT_STATE = SubBootState



class PubNode(NodeBase):
    _STATES = [EmptyState]
    _INIT_STATE = EmptyState

    def __init__(self, url):
        super().__init__(url)
        self.reactor.add_pub(url=url)
        self.reactor.notify_ready()

    def send_poke(self, poke_msg):
        poke = Poke.from_data(poke_msg)
        evl = Envelope.create(poke)
        self.reactor.pub(url=self.url, data=evl.serialize())


if __name__ == "__main__":
    import time
    print("yo its main time")

    pub = PubNode(url=URL)
    sub = SubNode(url=URL2)

    time.sleep(0.5)

    pub.send_poke('hihi its me')
    time.sleep(3)
    pub.send_poke('oh hai')


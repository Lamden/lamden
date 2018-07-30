"""
Working example that uses metaprogramming to dynamically route messages to receiver decorators

This version is NOT configured to work with StateMachine
"""

from cilantro.logger import get_logger
from cilantro.protocol.reactor import ReactorInterface
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase

class Poke(MessageBase):
    def serialize(self) -> bytes:
        return self._data.encode()

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data.decode()


def receive(msg_type):
    # TODO -- add validation to make sure @receive calls are receiving the correct message type
    def decorate(func):
        func._recv = msg_type
        return func
    return decorate


class NodeMeta(type):

    def __new__(cls, clsname, bases, clsdict):
        print("LogMeta NEW for class {}".format(clsname))
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        clsobj.log = get_logger(clsname)

        clsobj._receivers = {r._recv: r for r in clsdict.values() if hasattr(r, '_recv')}
        print("_receivers: ", clsobj._receivers)

        return clsobj


class NodeBase(metaclass=NodeMeta):

    def __init__(self, url):
        self.url = url
        self.reactor = ReactorInterface(self)

    def route(self, msg_binary: bytes):
        msg = None
        try:
            envelope = Envelope.from_bytes(msg_binary)
            msg = envelope.open()
        except Exception as e:
            self.log.error("Error opening envelope: {}".format(e))

        if type(msg) in self._receivers:
            self.log.debug("Routing msg: {}".format(msg))
            self._receivers[type(msg)](self, msg)
        else:
            self.log.error("Message {} has no implemented receiver in {}".format(msg, self._receivers))


class SubNode(NodeBase):
    def __init__(self, url, sub_urls=None):
        super().__init__(url)

        if sub_urls:
            for sub in sub_urls:
                self.log.info("Adding sub {}".format(sub))
                self.reactor.add_sub(url=sub, callback='route')

        self.reactor.notify_ready()

    @receive(Poke)
    def recv_poke(self, poke: Poke):
        self.log.critical("Got poke: {} with data {}!!".format(poke, poke._data))


class PubNode(NodeBase):
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
    URL = "tcp://127.0.0.1:5566"
    URL2 = "tcp://127.0.0.1:5577"
    URL3 = "tcp://127.0.0.1:5588"
    URL4 = "tcp://127.0.0.1:5599"

    pub = PubNode(url=URL)
    sub = SubNode(url=URL2, sub_urls=[URL])

    time.sleep(0.5)

    pub.send_poke('hihi its me')


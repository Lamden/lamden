from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.protocol.executors.base import ExecutorBase
from collections import defaultdict
from cilantro_ee.protocol.states.state import StateInput
import zmq.asyncio
import time


class SubPubExecutor(ExecutorBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subs = defaultdict(dict)  # Subscriber socket
        self.pubs = {}  # Key is url, value is Publisher socket

    def _recv_pub_env(self, header: str, envelope: Envelope):
        self.log.spam("Recv'd pub envelope with header {} and env {}".format(header, envelope))
        self.router.route_callback(callback=StateInput.INPUT, message=envelope.message, envelope=envelope)

    def send_pub(self, url: str, filter: str, data: bytes):
        assert isinstance(filter, str), "'filter' arg must be a string not {}".format(filter)
        assert isinstance(data, bytes), "'data' arg must be bytes"
        assert url in self.pubs, "Attempted to pub to URL {} that is not in self.pubs {}".format(url, self.pubs)

        self.log.spam("Publishing to URL {} with envelope: {}".format(url, Envelope.from_bytes(data)))
        self.pubs[url].send_multipart([filter.encode(), data])

    def add_pub(self, url: str):
        assert url not in self.pubs, "Attempted to add pub on url {} that is already in self.pubs {}".format(url, self.pubs)

        self.log.socket("Creating publisher socket on url {}".format(url))
        # self.pubs[url] = self.ironhouse.secure_socket(
        #     self.context.socket(socket_type=zmq.PUB),
        #     self.ironhouse.secret, self.ironhouse.public_key)
        self.pubs[url] = self.context.socket(socket_type=zmq.PUB)
        self.pubs[url].bind(url)
        time.sleep(0.2)  # for late joiner syndrome (TODO i think we can do away wit this?)

    def add_sub(self, url: str, filter: str, vk: str=''):
        # TODO correctly pass in VK from composer
        assert isinstance(filter, str), "'filter' arg must be a string not {}".format(filter)
        # assert vk != self.ironhouse.vk, "Cannot subscribe to your own VK"

        if url not in self.subs:
            self.log.socket("Creating subscriber socket to {}".format(url))

            # curve_serverkey = self.ironhouse.vk2pk(vk)
            # self.subs[url]['socket'] = socket = self.ironhouse.secure_socket(
            #     self.context.socket(socket_type=zmq.SUB),
            #     self.ironhouse.secret, self.ironhouse.public_key,
            #     curve_serverkey=curve_serverkey)
            self.subs[url]['socket'] = socket = self.context.socket(socket_type=zmq.SUB)
            self.subs[url]['filters'] = []

            socket.connect(url)

        if filter not in self.subs[url]['filters']:
            self.log.debugv("Adding filter {} to sub socket at url {}".format(filter, url))
            self.subs[url]['filters'].append(filter)
            self.subs[url]['socket'].setsockopt(zmq.SUBSCRIBE, filter.encode())

        if not self.subs[url].get('future'):
            self.log.debugv("Starting listener event for subscriber socket at url {}".format(url))
            self.subs[url]['future'] = self.add_listener(self.recv_env_multipart,
                                                         socket=self.subs[url]['socket'],
                                                         callback_fn=self._recv_pub_env,
                                                         ignore_first_frame=True)
            self.notify_socket_connected(socket_type=zmq.SUB, vk=vk, url=url)

    def remove_sub(self, url: str):
        assert url in self.subs, "Attempted to remove a sub that was not registered in self.subs"
        self.subs[url]['future'].cancel()  # socket is closed in the asyncio.cancelled
        del self.subs[url]

    def remove_sub_filter(self, url: str, filter: str):
        assert isinstance(filter, str), "'filter' arg must be a string not {}".format(filter)
        assert url in self.subs, "Attempted to remove a sub that was not registered in self.subs"
        assert filter in self.subs[url]['filters'], "Attempted to remove a filter that was not associated with the url"
        self.subs[url]['filters'].remove(filter)
        if len(self.subs[url]['filters']) == 0:
            self.remove_sub(url)
        else:
            self.subs[url]['socket'].setsockopt(zmq.UNSUBSCRIBE, filter.encode())

    def remove_pub(self, url: str):
        assert url in self.pubs, "Remove pub command invoked but pub socket is not set"

        self.pubs[url].disconnect(url)
        self.pubs[url].close()
        del self.pubs[url]

    def teardown(self):
        for url in self.subs.copy():
            self.remove_sub(url)
        for url in self.pubs.copy():
            self.remove_pub(url)

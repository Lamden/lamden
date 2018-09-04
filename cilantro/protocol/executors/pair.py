from cilantro.protocol.executors.base import ExecutorBase, _HANDLER, _SOCKET
from collections import defaultdict
from cilantro.protocol.states.state import StateInput
from cilantro.messages.envelope.envelope import Envelope
import zmq.asyncio


class PairExecutor(ExecutorBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # keys for self.sockets is a URL (str) which maps to another dict, that has keys
        # 'socket' (a zmq socket) and 'handler' (a zmq future)
        self.sockets = defaultdict(dict)

    def _recv_env(self, envelope: Envelope):
        self.log.spam("Recv'd PAIR envelope {}".format(envelope))
        self.router.route_callback(callback=StateInput.INPUT, message=envelope.message, envelope=envelope)

    def send(self, url: str, data: bytes):
        assert url in self.sockets, "Attempted to send to URL {} that is not in self.sockets {}".format(url, self.sockets)
        assert isinstance(data, bytes), "'data' arg must be bytes"

        self.log.spam("Sending over pair socket at URL {} with data {}".format(url, data))
        self.sockets[url].send(data)

    def bind_pair(self, url: str, vk: str=''):
        # TODO correctly pass in VK from composer
        self._add_pair(should_bind=True, url=url, vk=vk)

    def connect_pair(self, url: str, vk: str=''):
        # TODO correctly pass in VK from composer
        self._add_pair(should_bind=False, url=url, vk=vk)

    def _add_pair(self, url: str, should_bind=True, vk: str=''):
        # TODO correctly pass in VK from composer
        assert url not in self.sockets, "URL {} is already in self.sockets {}".format(url, self.sockets)

        socket = self.context.socket(zmq.PAIR)

        if should_bind:
            self.log.socket("BINDING pair socket to url {}".format(url))
            socket.bind(url)
        else:
            self.log.socket("CONNECTING pair socket to url {}".format(url))
            socket.connect(url)

        future = self.add_listener(self.recv_env_multipart, socket=socket, callback_fn=self._recv_env,
                                   ignore_first_frame=True)
        self.sockets[_SOCKET] = socket
        self.sockets[_HANDLER] = future
        self.notify_socket_connected(socket_type=zmq.PAIR, vk=vk, url=url)



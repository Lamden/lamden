from cilantro_ee.protocol.executors.base import ExecutorBase, _HANDLER, _SOCKET
from collections import defaultdict
from cilantro_ee.protocol.states.state import StateInput
from cilantro_ee.messages.envelope.envelope import Envelope
import zmq.asyncio




class DealerRouterExecutor(ExecutorBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 'dealers' is a simple nested dict for holding sockets by URL as well as their associated recv handlers
        # key for 'dealers' is socket URL, and value is another dict with keys 'socket' (value is Socket instance)
        # and 'socket' (value is asyncio handler instance)
        self.dealers = defaultdict(dict)

        self.expected_replies = {}  # Dict where key is reply UUID and value is the asyncio timeout handler

        # Router socket and recv handler
        self.router_socket = None
        self.router_handler = None

    def _recv_request_env(self, header: str, envelope: Envelope):
        self.log.spam("Recv REQUEST envelope with header {} and envelope {}".format(header, envelope))
        self.router.route_callback(callback=StateInput.REQUEST, header=header, message=envelope.message, envelope=envelope)

    def _recv_reply_env(self, header: str, envelope: Envelope):
        self.log.spam("Recv REPLY envelope with header {} and envelope {}".format(header, envelope))

        reply_uuid = envelope.meta.uuid
        if reply_uuid in self.expected_replies:
            self.log.debug("Removing reply with uuid {} from expected replies".format(reply_uuid))
            self.expected_replies[reply_uuid].cancel()
            del(self.expected_replies[reply_uuid])

        self.router.route_callback(callback=StateInput.INPUT, header=header, message=envelope.message, envelope=envelope)

    def _timeout(self, url: str, envelope: Envelope, reply_uuid: int):
        assert reply_uuid in self.expected_replies, "Timeout triggered but reply_uuid was not in expected_replies"

        self.log.debug("Request to url {} timed out! reply uuid {}".format(url, reply_uuid))
        del(self.expected_replies[reply_uuid])

        self.router.route_callback(callback=StateInput.TIMEOUT, message=envelope.message, envelope=envelope)

    def add_router(self, url: str):
        assert self.router_socket is None, "Attempted to add router on url {} but socket already configured".format(url)

        self.log.socket("Creating router socket on url {}".format(url))
        self.router_socket = self.context.socket(socket_type=zmq.ROUTER)
        # self.router = self.ironhouse.secure_socket(
        #     self.context.socket(socket_type=zmq.ROUTER),
        #     self.ironhouse.secret, self.ironhouse.public_key)
        self.router_socket.bind(url)

        self.router_handler = self.add_listener(self.recv_env_multipart, socket=self.router_socket,
                                                callback_fn=self._recv_request_env)

    def add_dealer(self, url: str, id: str, vk: str=''):
        # assert vk != self.ironhouse.vk, "Cannot subscribe to your own VK"
        if url in self.dealers:
            self.log.warning("Attempted to add dealer {} that is already in self.dealers".format(url))
            return

        assert isinstance(id, str), "'id' arg must be a string"
        self.log.socket("Creating dealer socket for url {} with id {}".format(url, id))

        # curve_serverkey = self.ironhouse.vk2pk(vk)
        # socket = self.ironhouse.secure_socket(
        #     self.context.socket(socket_type=zmq.DEALER),
        #     self.ironhouse.secret, self.ironhouse.public_key,
        #     curve_serverkey=curve_serverkey)
        socket = self.context.socket(socket_type=zmq.DEALER)
        socket.identity = id.encode('ascii')

        self.log.socket("Dealer socket connecting to url {}".format(url))
        socket.connect(url)

        future = self.add_listener(self.recv_env_multipart, socket=socket, callback_fn=self._recv_reply_env,
                                   ignore_first_frame=True)

        self.dealers[url][_SOCKET] = socket
        self.dealers[url][_HANDLER] = future

        self.notify_socket_connected(socket_type=zmq.DEALER, vk=vk, url=url)

    # TODO pass in the intended replier's vk so we can be sure the reply we get is actually from him
    def request(self, url: str, reply_uuid: str, envelope: Envelope, timeout=0):
        self.log.spam("requesting /w reply uuid {} and env {}".format(reply_uuid, envelope))
        assert url in self.dealers, "Attempted to make request to url {} that is not in self.dealers {}"\
            .format(url, self.dealers)

        reply_uuid = int(reply_uuid)
        timeout = float(timeout)

        self.log.spam("Composing request to url {}\ntimeout: {}\nenvelope: {}".format(url, timeout, envelope))

        if timeout > 0:
            assert reply_uuid not in self.expected_replies, "Reply UUID is already in expected replies"
            self.log.spam("Adding timeout of {} for reply uuid {}".format(timeout, reply_uuid))
            self.expected_replies[reply_uuid] = self.loop.call_later(timeout, self._timeout, url, envelope, reply_uuid)

        self.dealers[url][_SOCKET].send_multipart([envelope.serialize()])

    def reply(self, id: str, envelope: bytes):
        assert self.router_socket, "Attempted to reply but router socket is not set"
        assert isinstance(id, str), "'id' arg must be a string"
        assert isinstance(envelope, bytes), "'envelope' arg must be bytes"
        self.router_socket.send_multipart([id.encode(), envelope])

    def remove_router(self):
        assert self.router_socket, "Tried to remove router but self.router is not set"

        self.router_handler.cancel()
        # self.log.info("Removing router at url {}".format(url))

    def remove_dealer(self, url, id=''):
        assert url in self.dealers, "Attempted to remove dealer url {} that is not in list of dealers {}"\
            .format(url, self.dealers)

        self.log.notice("Removing dealer at url {} with id {}".format(url, id))

        socket = self.dealers[url][_SOCKET]
        future = self.dealers[url][_HANDLER]

        # Clean up socket and cancel future
        future.cancel()
        socket.close()

        # 'destroy' references to socket/future (not sure if this is necessary tbh)
        self.dealers[url][_SOCKET] = None
        self.dealers[url][_HANDLER] = None
        del(self.dealers[url])

    def teardown(self):
        for url in self.dealers.copy():
            self.remove_dealer(url)
        if self.router_socket:
            self.remove_router()
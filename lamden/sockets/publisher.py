import zmq
import zmq.asyncio
import asyncio
from lamden.logger.base import get_logger
from contracting.db.encoder import encode
import json

EXCEPTION_NO_ADDRESS_INFO = "Publisher has no address information."

EXCEPTION_TOPIC_STR_NOT_STRING = "argument 'topic_str' should be type string."
EXCEPTION_MSG_NOT_DICT = "argument 'msg_dict' should be type dict."
EXCEPTION_TOPIC_BYTES_NOT_BYTES = "argument 'topic_bytes' should be type bytes."
EXCEPTION_MSG_BYTES_NOT_BYTES = "argument 'msg_bytes' should be type bytes."

TOPIC_NEW_PEER_CONNECTION = "new_peer_connection"

class Publisher():
    def __init__(self, ctx: zmq.Context = None, network_ip: str = None):
        # Configure the listening socket
        self.network_ip = network_ip
        self.address = None
        self.socket = None

        self.ctx = ctx or zmq.asyncio.Context().instance()

        self.running = False

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def has_address(self) -> bool:
        return self.address is not None

    @property
    def socket_is_bound(self) -> bool:
        try:
            return len(self.socket.LAST_ENDPOINT) > 0
        except AttributeError:
            return False

    @property
    def socket_is_closed(self) -> bool:
        try:
            return self.socket.closed
        except AttributeError:
            return True

    def log(self, log_type: str, message: str) -> None:
        if self.network_ip:
            named_message = f'[PUBLISHER] {message}'
            print(f'[{self.network_ip}]{named_message}\n')
        else:
            named_message = message
            print(f'[PUBLISHER] {named_message}\n')

        logger_name = self.network_ip or 'PUBLISHER'
        logger = get_logger(logger_name)
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

    def start(self) -> None:
        if self.running:
            self.log('warning', 'Already running.')
            return

        self.create_socket()
        self.connect_socket()

        self.log('info', f'Starting on {self.address}')

        self.running = True

    def create_socket(self) -> None:
        if self.socket_is_bound:
            return
        self.socket = self.ctx.socket(zmq.PUB)

    def connect_socket(self) -> None:
        if not self.has_address:
            raise AttributeError(EXCEPTION_NO_ADDRESS_INFO)

        if self.socket_is_bound:
            return
        if "*" in self.address:
            self.socket.bind(self.address)
        else:
            self.socket.connect(self.address)

    def set_address(self, ip: str = "*", port: int = 19080) -> None:
        if not isinstance(ip, str):
            raise TypeError("Ip must be type string.")

        if not isinstance(port, int):
            raise TypeError("Port must be type integer.")

        self.address = f'tcp://{ip}:{port}'
    
    def publish(self, topic_str: str, msg_dict: dict) -> None:
        if not self.running:
            self.log('error', 'Publisher is not running.')
            return

        if not isinstance(topic_str, str):
            raise TypeError(EXCEPTION_TOPIC_STR_NOT_STRING)

        if not isinstance(msg_dict, dict):
            raise TypeError(EXCEPTION_MSG_NOT_DICT)

        self.log('info', f'Publishing ({topic_str}): {msg_dict}')

        msg_bytes = encode(msg_dict).encode()

        self.send_multipart_message(topic_bytes=topic_str.encode('UTF-8'), msg_bytes=msg_bytes)

    def send_multipart_message(self, topic_bytes: bytes, msg_bytes: bytes) -> None:
        if not isinstance(topic_bytes, bytes):
            raise TypeError(EXCEPTION_TOPIC_BYTES_NOT_BYTES)

        if not isinstance(msg_bytes, bytes):
            raise TypeError(EXCEPTION_MSG_BYTES_NOT_BYTES)

        self.socket.send_multipart([topic_bytes, msg_bytes])

    def announce_new_peer_connection(self, vk: str, ip: str) -> None:
        self.publish(
            topic_str=TOPIC_NEW_PEER_CONNECTION,
            msg_dict={
                'vk': vk,
                'ip': ip
            }
        )
    
    def stop(self) -> None:
        if self.running:
            self.running = False

            self.log('info', 'Stopping.')

            if self.socket:
                self.socket.close()
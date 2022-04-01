import zmq
import zmq.asyncio
import asyncio
from lamden.logger.base import get_logger
from contracting.db.encoder import encode

EXCEPTION_NO_ADDRESS_INFO = "Publisher has no address information."

class Publisher():
    def __init__(self, logger=None):
        # Configure the listening socket
        self.log = logger or get_logger("PUBLISHER")

        self.address = None
        self.socket = None

        self.ctx = self.ctx = zmq.asyncio.Context().instance()

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

    def start(self) -> None:
        if self.running:
            self.log.warning(f'[PUBLISHER] Already running.')
            print(f'[{self.log.name}][PUBLISHER] Already running.')
            return

        self.create_socket()
        self.connect_socket()

        self.log.info(f'[PUBLISHER] Starting on {self.address}')
        print(f'[{self.log.name}][PUBLISHER] Starting on {self.address}')

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

        self.socket.bind(self.address)

    def set_address(self, ip: str = '*', port: int = 19080) -> None:
        self.address = f'tcp://{ip}:{port}'
    
    def publish(self, topic, msg) -> None:
        if not self.running:
            self.log.error(f'[PUBLISHER] Publisher is not running.')
            print(f'[{self.log.name}][PUBLISHER] Publisher is not running.')
            return

        self.log.error(f'[PUBLISHER] Publishing: {msg}')
        print(f'[{self.log.name}][PUBLISHER] Publishing: {msg}')
        self.debug_published.append(msg)

        m = encode(msg).encode()        
        self.socket.send_string(topic, flags=zmq.SNDMORE)
        self.socket.send(m)

    def announce_new_peer_connection(self, vk: str, ip: str):
        topic = "new_peer_connection"
        msg = {
            'vk': vk,
            'ip': ip
        }

        self.publish(
            topic=topic,
            msg=msg
        )
    
    def stop(self):
        if self.running:
            self.running = False

            self.log.info('[PUBLISHER] Stopping.')
            print(f'[{self.log.name}][PUBLISHER] Stopping.')

            if self.socket:
                self.socket.close()



        
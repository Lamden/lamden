from lamden.logger.base import get_logger
import asyncio
import zmq
from lamden.crypto.wallet import Wallet
from lamden.crypto.z85 import z85_key
from lamden.crypto.challenges import create_challenge, verify_challenge
from lamden.sockets.request import Request, Result
from lamden.sockets.subscriber import Subscriber
from lamden.sockets.publisher import TOPIC_NEW_PEER_CONNECTION

from typing import Callable
from urllib.parse import urlparse

from contracting.db.encoder import decode, encode

SUBSCRIPTIONS = ["work", TOPIC_NEW_PEER_CONNECTION, "contenders", "health"]

ACTION_PING = "ping"
ACTION_HELLO = "hello"
ACTION_GET_LATEST_BLOCK = 'get_latest_block'
ACTION_GET_BLOCK = "get_block"
ACTION_GET_NEXT_BLOCK = "get_next_block"
ACTION_GET_NETWORK_MAP = "get_network_map"

class Peer:
    def __init__(self, ip: str, server_vk: str, local_wallet: Wallet, get_network_ip: Callable,
                 services: Callable = None, connected_callback: Callable = None, socket_ports: dict = None,
                 ctx: zmq.Context = None, local: bool = False):

        self.ctx = ctx
        self.server_vk = server_vk
        self.server_curve_vk = z85_key(server_vk)

        self.get_network_ip = get_network_ip
        self.local = local

        self.protocol = 'tcp://'

        try:
            self.socket_ports = dict(socket_ports)
        except TypeError:
            self.socket_ports = dict({
                'router': 19000,
                'publisher': 19080,
                'webserver': 18080
            })

        self.url = None
        self.set_ip(ip)

        self.services = services
        self.in_consensus = True
        self.errored = False
        self.local_wallet = local_wallet

        self.running = False
        self.connected = False
        self.verified = False

        self.reconnecting = False
        self.connected_callback = connected_callback

        self.request = None
        self.subscriber = None

        self.latest_block_info = dict({
            'number': 0,
            'hlc_timestamp': "0"
        })

        self.verify_task = None
        self.reconnect_task = None

        self.setup_event_loop()

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    @property
    def local_vk(self) -> str:
        return self.local_wallet.verifying_key

    @property
    def ip(self) -> [str, None]:
        if not self.url:
            return None
        return self.url.hostname

    @property
    def latest_block_number(self) -> int:
        return self.latest_block_info.get('number')

    @property
    def latest_block_hlc_timestamp(self) -> str:
        return self.latest_block_info.get('hlc_timestamp')

    @property
    def subscriber_address(self) -> str:
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('publisher'))

    @property
    def request_address(self) -> str:
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('router'))

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_connected(self) -> bool:
        return self.connected

    @property
    def is_verified(self) -> bool:
        return self.verified

    @property
    def is_verifying(self) -> bool:
        if self.verify_task is None:
            return False
        return not self.verify_task.done()

    def log(self, log_type: str, message: str) -> None:
        named_message = f'[PEER] {message}'

        logger = get_logger(f'{self.get_network_ip()}')
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

    def setup_event_loop(self):
        try:
            self.loop = asyncio.get_event_loop()

            if self.loop.is_closed():
                self.loop = None

        except RuntimeError:
            pass

        if not self.loop:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def setup_subscriber(self) -> None:
        self.subscriber = Subscriber(
            address=self.subscriber_address,
            topics=SUBSCRIPTIONS,
            callback=self.process_subscription,
            local_ip=self.get_network_ip(),
            local=self.local,
            ctx=self.ctx
        )
        self.subscriber.start()

    def setup_request(self) -> None:
        self.request = Request(
            server_curve_vk=self.server_curve_vk,
            local_wallet=self.local_wallet,
            local_ip=self.get_network_ip(),
            to_address=self.request_address,
            ctx=self.ctx
        )
        self.request.start()

    def is_available(self) -> bool:
        tasks = asyncio.gather(
            self.ping()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        pong = res[0]
        return pong is not None

    def set_ip(self, address: str) -> None:
        self.url = urlparse(address)

        if not self.url.hostname:
            self.set_ip(address=f'{self.protocol}{address}')
        else:
            if self.url.port:
                self.socket_ports['router'] = self.url.port
                self.calc_ports()

    def set_request_ip(self):
        if self.request is not None:
            self.request.to_address = self.request_address

    def set_latest_block_number(self, number: int) -> None:
        if isinstance(number, int):
            self.latest_block_info['number'] = number

    def set_latest_block_hlc_timestamp(self, hlc_timestamp: str) -> None:
        if isinstance(hlc_timestamp, str):
            self.latest_block_info['hlc_timestamp'] = hlc_timestamp

    def set_latest_block_info(self, number: int, hlc_timestamp: str) -> None:
        if isinstance(number, int) and isinstance(hlc_timestamp, str):
            self.set_latest_block_number(number=number)
            self.set_latest_block_hlc_timestamp(hlc_timestamp=hlc_timestamp)

    def calc_ports(self) -> None:
        self.socket_ports['publisher'] = 19080 + (self.socket_ports['router'] - 19000)
        self.socket_ports['webserver'] = 18080 + (self.socket_ports['router'] - 19000)

    def start(self, verify: bool = True) -> None:
        if self.running:
            self.log('warning', 'Already running.')
            return

        if not self.request:
            self.setup_request()

        self.running = True

        if verify:
            self.start_verify_peer_loop()

    def start_verify_peer_loop(self) -> None:
        if self.is_verifying:
            return

        self.verify_task = asyncio.ensure_future(self.verify_peer_loop())

    async def verify_peer_loop(self) -> None:
        self.verified = False

        while not self.verified and self.running:
            # wait till peer is available
            await self.reconnect_loop()

            if self.running:
                # Validate peer is correct
                await self.verify_peer()

                await asyncio.sleep(1)

    async def verify_peer(self):
        self.verified = False

        res = await self.hello()

        if res is not None and res.get('success') and self.running:
            response_type = res.get('response')
            if response_type == 'hello':
                self.store_latest_block_info(
                    latest_block_num=int(res.get('latest_block_number')),
                    latest_hlc_timestamp=res.get('latest_hlc_timestamp')
                )

                self.log('info', 'Received response from authorized node with pub info.')

                if not self.subscriber:
                    self.log('info', f'Setting up Subscriber to {self.subscriber_address}')
                    self.setup_subscriber()

                    if self.connected_callback is not None:
                        self.connected_callback(peer_vk=self.server_vk)

                self.verified = True
        else:
            self.log('error', f'Failed to validate {self.server_vk} at ({self.request_address})')

    def store_latest_block_info(self, latest_block_num: int, latest_hlc_timestamp: str) -> None:
        if not isinstance(latest_block_num, int) or not isinstance(latest_hlc_timestamp, str):
            self.log('info', f'Unable to set latest block info with number {latest_block_num} and \
             {latest_hlc_timestamp}')
            return

        self.latest_block_info = dict({
            'number': int(latest_block_num),
            'hlc_timestamp': latest_hlc_timestamp
        })

    async def process_subscription(self, data: list) -> None:
        if self.services is None:
            raise AttributeError("Cannot process subscription messages, services not setup.")

        try:
            topic, msg = data
        except ValueError as err:
            print(data)
            self.log('error', f'ERROR in message: {err}')
            return

        try:
            msg_str = decode(msg)
            topic_str = topic.decode("utf-8")

        except Exception as err:
            self.log('error', f'ERROR decoding message parts: {err}')
            return

        services = self.services()

        processor = services.get(topic_str)

        if processor is not None and msg_str is not None:
            asyncio.ensure_future(processor.process_message(msg_str))

    async def test_connection(self) -> bool:
        connected = await self.ping()
        if connected:
            return True

        self.connected = False
        self.reconnect()
        return False

    def reconnect(self) -> None:
        if self.reconnecting:
            return

        self.reconnect_task = asyncio.ensure_future(self.reconnect_loop())

    async def reconnect_loop(self) -> None:
        #self.log('info', 'Waiting 10 seconds before starting reconnect loop...')
        await asyncio.sleep(2)

        if self.reconnecting or not self.running:
            return

        self.reconnecting = True

        while not self.connected:
            if not self.running:
                self.reconnecting = False
                return

            res = await self.ping()

            if res:
                self.connected = True
            else:
                self.log('info', f'Could not ping {self.request_address}. Attempting to reconnect...')
                await asyncio.sleep(1)

        self.log('info', f'Reconnected to {self.request_address}!')
        self.reconnecting = False

    async def update_ip(self, new_ip):
        verify_res = await self.verify_new_ip(new_ip=new_ip)

        if verify_res is None:
            return

        challenge = verify_res.get('challenge')
        challenge_response = verify_res.get('challenge_response')

        if verify_challenge(peer_vk=self.server_vk, challenge=challenge, challenge_response=challenge_response):
            self.log('info', f"Updating peer {self.server_vk}'s IP from {self.request_address} to {new_ip}.")
            self.set_ip(address=new_ip)
            asyncio.ensure_future(self.restart())

    async def restart(self):
        await self.stop()

        self.running = False
        self.connected = False
        self.verified = False
        self.reconnecting = False
        self.request = None
        self.subscriber = None

        self.latest_block_info = dict({
            'number': 0,
            'hlc_timestamp': "0"
        })

        self.verify_task = None

        self.start()

    async def ping(self) -> dict:
        msg_obj = {'action': ACTION_PING}
        msg_json = await self.send_request(msg_obj=msg_obj, timeout=15000, attempts=1)
        return msg_json

    async def hello(self) -> (dict, None):
        challenge = create_challenge()
        msg_obj = {'action': ACTION_HELLO, 'ip': self.get_network_ip(), 'challenge': challenge}
        msg_json = await self.send_request(msg_obj=msg_obj, timeout=15000, attempts=1)
        if msg_json:
            msg_json['challenge'] = challenge
        return msg_json

    async def verify_new_ip(self, new_ip) -> (dict, None):
        challenge = create_challenge()
        msg_obj = {'action': ACTION_HELLO, 'ip': self.get_network_ip(), 'challenge': challenge}
        msg_json = await self.send_request(msg_obj=msg_obj, timeout=15000, attempts=1)
        if msg_json:
            msg_json['challenge'] = challenge
        return msg_json

    async def get_latest_block_info(self) -> (dict, None):
        msg_obj = {'action': ACTION_GET_LATEST_BLOCK}
        msg_json = await self.send_request(msg_obj=msg_obj, timeout=15000, attempts=1)
        if isinstance(msg_json, dict):
            if msg_json.get('response') == ACTION_GET_LATEST_BLOCK:
                self.set_latest_block_info(
                    number=int(msg_json.get('latest_block_number')),
                    hlc_timestamp=msg_json.get('latest_hlc_timestamp')
                )
        return msg_json

    async def get_block(self, block_num: int = None, hlc_timestamp: str = None) -> (dict, None):
        msg_obj = {'action': ACTION_GET_BLOCK, 'block_num': int(block_num) if block_num is not None else block_num, 'hlc_timestamp': hlc_timestamp}
        msg_json = await self.send_request(msg_obj=msg_obj, attempts=3, timeout=15000)
        return msg_json

    async def get_next_block(self, block_num: int) -> (dict, None):
        msg_obj = {'action': ACTION_GET_NEXT_BLOCK, 'block_num': int(block_num)}
        msg_json = await self.send_request(msg_obj=msg_obj, attempts=3, timeout=15000)
        return msg_json

    async def get_network_map(self) -> (dict, None):
        msg_obj = {'action': ACTION_GET_NETWORK_MAP}
        msg_json = await self.send_request(msg_obj=msg_obj, timeout=15000, attempts=5)
        return msg_json

    async def send_request(self, msg_obj: dict, timeout: int = 200,
                           attempts: int = 3) -> (dict, None):

        if not self.request:
            raise AttributeError("Request socket not setup.")

        if msg_obj is None:
            return None

        try:
            str_msg = encode(msg_obj)
        except Exception as err:
            self.log('error', f'{err}')
            self.log('info', f'Failed to encode message {msg_obj} to bytes.')

            return None

        try:
            result = await self.request.send(str_msg=str_msg, timeout=timeout, attempts=attempts)
            return self.handle_result(result=result)
        except Exception as error:
            print(error)

    def handle_result(self, result: Result) -> (dict, None):
        if result.success:
            self.connected = True
            try:
                msg_json = decode(result.response)
                msg_json['success'] = result.success
                return msg_json

            except Exception as err:
                self.log('error', f'{err}')
                self.log('info', f'Failed to decode json from {self.request_address}: {result.__dict__}')
        else:
            if result.error:
                self.log('error', f'Result Error: {result.error}')

            self.connected = False

            if not self.reconnecting:
                self.reconnect()

        return None

    async def cancel_reconnect_task(self):
        if self.reconnect_task:
            if not self.reconnect_task.done():
                while not self.reconnect_task.done():
                    await asyncio.sleep(0.1)
                self.reconnecting = False

    async def cancel_verify_task(self):
        if self.is_verifying:
            if not self.verify_task.done():
                while not self.verify_task.done():
                    await asyncio.sleep(0.1)

    async def stopping(self):
        await self.cancel_reconnect_task()

        if not self.reconnecting and not self.is_verifying:
            return

        while self.reconnecting or self.is_verifying:
            await asyncio.sleep(0.01)

    async def stop(self) -> None:
        self.running = False

        await self.cancel_reconnect_task()
        await self.cancel_verify_task()

        if self.request:
            await self.request.stop()
        if self.subscriber:
            await self.subscriber.stop()

        await self.stopping()

        self.log('info', 'Stopped.')

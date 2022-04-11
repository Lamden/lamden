import json
from lamden.logger.base import get_logger
import asyncio
from lamden.crypto.wallet import Wallet
from lamden.crypto.z85 import z85_key
from lamden.sockets.request import Request, Result
from lamden.sockets.subscriber import Subscriber

from typing import Callable
from urllib.parse import urlparse

LATEST_BLOCK_INFO = 'latest_block_info'
GET_BLOCK = 'get_block'

SUBSCRIPTIONS = ["work", "new_peer_connection", "contenders"]

class Peer:
    def __init__(self, ip: str, server_vk: str, local_wallet: Wallet, get_network_ip: Callable,
                  services: dict = None, connected_callback: Callable = None):

        self.server_vk = server_vk
        self.server_z85_key = z85_key(server_vk)

        self.get_network_ip = get_network_ip

        self.protocol = 'tcp://'
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

        self.sub_running = False
        self.reconnecting = False
        self.connected_callback = connected_callback

        self.request = None
        self.subscriber = None

        self.latest_block_info = dict({
            'number': 0,
            'hlc_timestamp': "0"
        })

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    @property
    def local_vk(self) -> str:
        return self.local_wallet.verifying_key

    @property
    def ip(self) -> str:
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
        self.log('info', 'PUBLISHER ADDRESS: {}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('publisher')))
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('publisher'))

    @property
    def request_address(self) -> str:
        self.log('info', 'ROUTER ADDRESS: {}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('router')))
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('router'))

    @property
    def is_running(self) -> bool:
        if not self.subscriber or not self.request:
            return False

        return self.request.is_running and self.subscriber.is_running

    @property
    def is_connected(self) -> bool:
        return self.connected

    @property
    def is_verified(self) -> bool:
        return self.verified

    def log(self, log_type: str, message: str) -> None:
        named_message = f'[ROUTER]{message}'

        logger = get_logger(f'{self.address}')
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

        print(f'[{self.address}]{named_message}')

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

    def start(self) -> None:
        if self.running:
            self.log('warning', 'Already running.')
            return

        if not self.request:
            self.setup_request()

        self.running = True

        asyncio.ensure_future(self.verify_peer_loop())

    async def verify_peer_loop(self) -> None:
        while not self.verified:
            # wait till peer is available
            await self.reconnect_loop()

            # Validate peer is correct
            await self.verify_peer()

            await asyncio.sleep(1)

    async def verify_peer(self):
        self.verified = False

        res = await self.hello()

        if res is not None and res.get('success'):
            response_type = res.get('response')
            if response_type == 'hello':
                self.store_latest_block_info(
                    latest_block_num=res.get('latest_block_num'),
                    latest_hlc_timestamp=res.get('latest_hlc_timestamp')
                )

                self.log('info', 'Received response from authorized node with pub info.')

                if not self.subscriber:
                    self.setup_subscriber()

                    if self.connected_callback is not None:
                        self.connected_callback(vk=self.local_vk)

                self.verified = True
        else:
            self.log('error', f'Failed to validate {self.server_vk} at ({self.request_address})')

    def store_latest_block_info(self, latest_block_num: int, latest_hlc_timestamp: str) -> None:
        if not isinstance(latest_block_num, int) or not isinstance(latest_hlc_timestamp, str):
            self.log('info', f'Unable to set latest block info with number {latest_block_num} and {latest_hlc_timestamp}')
            return

        self.latest_block_info = dict({
            'number': latest_block_num,
            'hlc_timestamp': latest_hlc_timestamp
        })

    def setup_subscriber(self) -> None:
        self.subscriber = Subscriber(
            address=self.subscriber_address,
            topics=SUBSCRIPTIONS,
            callback=self.process_subscription,
            logger=self.log
        )
        self.subscriber.start()

    def setup_request(self) -> None:
        self.request = Request(
            server_vk=self.server_z85_key,
            local_wallet=self.local_wallet,
            logger=self.log
        )

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
            msg_str = json.loads(msg)
            topic_str = topic.decode("utf-8")
        except Exception as err:
            self.log('error', f'ERROR decoding message parts: {err}')
            return

        services = self.services()

        processor = services.get(topic_str)

        if processor is not None and msg_str is not None:
            await processor.process_message(msg_str)

    def reconnect(self) -> None:
        asyncio.ensure_future(self.reconnect_loop())

    async def reconnect_loop(self) -> None:
        if self.reconnecting:
            return

        self.reconnecting = True

        while not self.connected:
            if not self.running:
                self.reconnecting = False
                return

            res = await self.ping()

            if res is None:
                self.log('info', f'Could not ping {self.request_address}. Attempting to reconnect...')
                await asyncio.sleep(1)

        self.log('info', f'Reconnected to {self.request_address}!')

        self.connected = True
        self.reconnecting = False

    async def ping(self) -> dict:
        msg_obj = {'action': 'ping'}
        msg_json = await self.send_request(msg_obj=msg_obj, timeout=500, retries=5)
        return msg_json

    async def hello(self) -> (dict, None):
        msg_obj = {'action': 'hello', 'ip': self.get_network_ip()}
        msg_json = await self.send_request(msg_obj=msg_obj, timeout=500, retries=5)
        return msg_json

    async def get_latest_block_info(self) -> (dict, None):
        msg_obj = {'action': 'latest_block_info'}
        msg_json = await self.send_request(msg_obj=msg_obj)
        if isinstance(msg_json, dict):
            if msg_json.get('response') == LATEST_BLOCK_INFO:
                self.set_latest_block_info(
                    number=msg_json.get('latest_block_number'),
                    hlc_timestamp=msg_json.get('latest_hlc_timestamp')
                )
        return msg_json

    async def get_block(self, block_num: int) -> (dict, None):
        msg_obj = {'action': 'get_block', 'block_num': block_num}
        msg_json = await self.send_request(msg_obj=msg_obj)
        return msg_json

    async def get_node_list(self) -> (dict, None):
        msg_obj = {'action': 'get_node_list'}
        msg_json = await self.send_request(msg_obj=msg_obj)
        return msg_json

    async def send_request(self, msg_obj: dict, timeout: int=200, retries: int=3) -> (dict, None):
        if not self.request:
            raise AttributeError("Request socket not setup.")

        if msg_obj is None:
            return None

        try:
            str_msg = json.dumps(msg_obj)
        except Exception as err:
            self.log('error', f'{err}')
            self.log('info', f'Failed to encode message {msg_obj} to bytes.')

            return None

        result = await self.request.send(to_address=self.request_address, str_msg=str_msg, timeout=timeout, retries=retries)

        return self.handle_result(result=result)

    def handle_result(self, result: Result) -> (dict, None):
        if result.success:
            self.connected = True
            try:
                msg_json = json.loads(result.response)
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

    def stop(self) -> None:
        self.running = False
        if self.request:
            self.request.stop()
        if self.subscriber:
            self.subscriber.stop()
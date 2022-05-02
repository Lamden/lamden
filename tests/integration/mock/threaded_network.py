import asyncio
import threading

from lamden.network import Network, ACTION_GET_LATEST_BLOCK
from lamden.crypto.wallet import Wallet

class ThreadedNetwork(threading.Thread):
    def __init__(self, driver, socket_ports: dict, wallet: Wallet = None ):
        threading.Thread.__init__(self)

        self.daemon = True

        self.driver = driver
        self.socket_ports = socket_ports
        self.wallet = wallet or Wallet()
        self.loop = None
        self.n = None

    @property
    def is_running(self) -> bool:
        if not self.n:
            return False
        return self.n.is_running

    @property
    def vk(self) -> str:
        if not self.n:
            return None
        return self.n.vk

    def get_latest_block(self):
        return {}

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.n = Network(
            wallet=self.wallet,
            socket_ports=self.socket_ports,
            driver=self.driver,
            local=True
        )

        self.n.add_action(ACTION_GET_LATEST_BLOCK, self.get_latest_block)

        self.n.start()

        while not self.n.all_sockets_stopped:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(asyncio.sleep(0))

        print('done')

    async def stop(self):
        await self.n.stop()
        print('Threaded Network Stopped.')
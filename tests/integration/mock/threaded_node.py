import asyncio
import threading

from lamden.nodes.delegate import Delegate
from lamden.nodes.masternode import Masternode

from lamden.storage import BlockStorage
from contracting.db.driver import ContractDriver, FSDriver

from lamden.crypto.wallet import Wallet

import unittest
from pathlib import Path
import shutil

node_class_map = {
    'masternode': Masternode,
    'delegate': Delegate
}

class ThreadedNode(threading.Thread, Masternode):
    def __init__(self,
                 node_type,
                 constitution: dict,
                 block_storage: BlockStorage,
                 driver: ContractDriver,
                 index=0,
                 bootnodes={},
                 bypass_catchup=False,
                 should_seed=True,
                 metering=False,
                 wallet: Wallet = None
                 ):

        threading.Thread.__init__(self)

        self.daemon = True

        self.node_type = node_type
        self.index = index
        self.constitution = constitution
        self.bootnodes = bootnodes

        self.driver = driver
        self.block_storage = block_storage

        self.bypass_catchup = bypass_catchup

        self.should_seed = should_seed
        self.metering = metering

        self.wallet = wallet or Wallet()

        self.loop = None
        self.node = None

    @property
    def is_running(self) -> bool:
        if not self.node:
            return False
        return self.node.running

    @property
    def vk(self) -> str:
        if not self.node:
            return None
        return self.node.wallet.verifying_key

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.node = node_class_map[self.node_type](
            wallet=self.wallet,
            socket_ports=self.create_socket_ports(index=self.index),
            driver=self.driver,
            blocks=self.block_storage,
            testing=True
        )

        self.node.network.local = True

        self.node.start()

        print('done')

    async def stop(self):
        if self.node.running:
            await self.node.stop()
            print('Threaded Network Stopped.')

class TestThreadedNode(unittest.TestCase):
    def setUp(self):
        self.node_wallet = Wallet()

        self.current_path = Path.cwd()
        self.test_fixture_dir = f'{self.current_path}/fixtures'
        self.node_dir = f'{self.test_fixture_dir}/nodes'
        self.node_state_dir = Path(f'{self.node_dir}/{self.node_wallet.verifying_key}/state')
        self.node_block_dir = Path(f'{self.node_dir}/{self.node_wallet.verifying_key}/blocks')

        self.node_state_dir.mkdir(parents=True, exist_ok=True)

        self.driver = ContractDriver(driver=FSDriver(root=Path(self.node_state_dir)))
        self.block_storage = BlockStorage(home=Path(self.node_block_dir))

        try:
            self.loop = asyncio.get_event_loop()
        except:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.node = None

    def tearDown(self):
        try:
            shutil.rmtree(self.test_fixture_dir)
        except:
            pass

        if self.node:
            self.stop_threaded_node()

        if not self.loop.is_closed():
            self.loop.stop()
            self.loop.close()

    def stop_threaded_node(self):
            self.loop.run_until_complete(self.node.stop())

    def test_can_create_threaded_node_instance__raises_no_errors(self):
        try:
            self.node = ThreadedNode(
                node_type='masternode',
                constitution={},
                driver=self.driver,
                block_storage=self.block_storage,
                wallet=self.node_wallet
            )
        except Exception as err:
            print(err)
            self.fail("Threaded Node should run and raise no exceptions.")

        self.assertIsInstance(self.node, ThreadedNode)

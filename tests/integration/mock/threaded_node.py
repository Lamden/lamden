import asyncio
import threading
import time

from lamden.nodes.delegate import Delegate
from lamden.nodes.masternode import Masternode
from lamden.nodes.base import Node

from lamden.storage import BlockStorage
from contracting.db.driver import ContractDriver, FSDriver
from lamden.network import Network

from lamden.crypto.wallet import Wallet
from lamden.nodes.filequeue import FileQueue

import unittest
from pathlib import Path
import shutil

node_class_map = {
    'masternode': Masternode,
    'delegate': Delegate
}

class ThreadedNode(threading.Thread):
    def __init__(self,
                 node_type,
                 constitution: dict,
                 block_storage: BlockStorage,
                 raw_driver,
                 tx_queue: FileQueue = FileQueue(),
                 index=0,
                 bootnodes={},
                 bypass_catchup=False,
                 should_seed=True,
                 metering=False,
                 wallet: Wallet = None,
                 genesis_path: str = str(Path.cwd()),
                 reconnect_attempts=60):

        threading.Thread.__init__(self)

        self.daemon = True

        self.node_type = node_type
        self.index = index
        self.constitution = constitution
        self.bootnodes = bootnodes

        self.raw_driver = raw_driver
        self.contract_driver = ContractDriver(driver=self.raw_driver)
        self.block_storage = block_storage
        self.genesis_path = genesis_path
        self.tx_queue = tx_queue

        self.bypass_catchup = bypass_catchup

        self.should_seed = should_seed
        self.metering = metering

        self.wallet = wallet or Wallet()

        self.running = False
        self.loop = None
        self.node: Node = None

        self.err = None

        self.reconnect_attempts = reconnect_attempts

    @property
    def node_started(self) -> bool:
        if not self.node:
            return False
        return self.node.started

    @property
    def vk(self) -> str:
        if not self.node:
            return None
        return self.node.wallet.verifying_key

    @property
    def ip(self) -> str:
        if not self.node:
            return None
        return self.node.network.external_address

    @property
    def network(self) -> Network:
        if not self.node:
            return None
        return self.node.network

    @property
    def main_processing_queue(self):
        if not self.node:
            return None
        return self.node.main_processing_queue

    @property
    def validation_queue(self):
        if not self.node:
            return None
        return self.node.validation_queue

    @property
    def system_monitor(self):
        if not self.node:
            return None
        return self.node.system_monitor

    @property
    def node_is_running(self):
        if not self.node:
            return False
        return self.node.running

    @property
    def latest_block_height(self) -> int:
        block_info = self.node.network.get_latest_block_info()
        return block_info.get("number")

    @property
    def latest_hlc_timestamp(self) -> str:
        block_info = self.node.network.get_latest_block_info()
        return block_info.get("hlc_timestamp")

    @property
    def last_processed_hlc(self) -> str:
        return self.node.last_processed_hlc

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def start_node(self):
        asyncio.ensure_future(self.node.start())

    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            self.node = node_class_map[self.node_type](
                constitution=self.constitution,
                bootnodes=self.bootnodes,
                socket_base="",
                wallet=self.wallet,
                socket_ports=self.create_socket_ports(index=self.index),
                driver=self.contract_driver,
                blocks=self.block_storage,
                should_seed=self.should_seed,
                genesis_path=str(self.genesis_path),
                tx_queue=self.tx_queue,
                reconnect_attempts=self.reconnect_attempts
            )

            self.node.network.set_to_local()
            self.node.start_node()

            self.running = True

            print(f'Started Threaded Node {self.index}')

            # Keep Thread alive
            while self.running:
                self.sleep()

        except Exception as err:
            self.err = err

    def set_smart_contract_value(self, key: str, value: str):
        self.raw_driver.set(key=key, value=value)

    def get_smart_contract_value(self, key: str) -> any:
        return self.raw_driver.get(key=key)

    def get_latest_block(self) -> dict:
        return self.network.get_latest_block()

    def send_tx(self, encoded_tx: bytes):
        self.node.tx_queue.append(encoded_tx)

    def sleep(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.sleep(0))

    async def stop(self):
        if not self.node:
            return

        await self.node.stop()

        self.running = False
        print(f'Threaded Node ({self.node_type}) {self.index} Stopped.')

class TestThreadedNode(unittest.TestCase):
    def setUp(self):
        self.node_wallet = Wallet()

        self.current_path = Path.cwd()
        self.test_fixture_dir = f'{self.current_path}/fixtures'

        try:
            shutil.rmtree(self.test_fixture_dir)
        except:
            pass

        self.node_dir = f'{self.test_fixture_dir}/nodes'
        self.node_state_dir = Path(f'{self.node_dir}/{self.node_wallet.verifying_key}/state')
        self.node_block_dir = Path(f'{self.node_dir}/{self.node_wallet.verifying_key}/blocks')

        self.node_state_dir.mkdir(parents=True, exist_ok=True)

        self.driver = ContractDriver(driver=FSDriver(root=Path(self.node_state_dir)))
        self.block_storage = BlockStorage(home=Path(self.node_block_dir))


        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.tn = None

        self.nodes = []

    def tearDown(self):
        if self.tn:
            self.nodes.append(self.tn)

        for tn in self.nodes:
            self.stop_threaded_node(tn=tn)

        if not self.loop.is_closed():
            self.loop.stop()
            self.loop.close()

        self.tn = None

    def stop_threaded_node(self, tn):
            task = asyncio.ensure_future(tn.stop())
            while not task.done():
                self.async_sleep(0.1)

    def create_constitution(self, node_type: str) -> dict:
        if node_type == 'masternode':
            return {
                'masternodes': [self.node_wallet.verifying_key],
                'delegates': []
            }
        else:
            return {
                'masternodes': [],
                'delegates': [self.node_wallet.verifying_key]
            }

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_threaded_node_instance__raises_no_errors(self):
        node_type = 'masternode'

        try:
            self.tn = ThreadedNode(
                node_type=node_type,
                constitution=self.create_constitution(node_type=node_type),
                raw_driver=self.driver,
                block_storage=self.block_storage,
                wallet=self.node_wallet
            )
        except Exception as err:
            print(err)
            self.fail("Threaded Node should run and raise no exceptions.")

        self.assertIsInstance(self.tn, ThreadedNode)

    def test_start__creates_started_masternode_instance_raises_no_errors(self):
        node_type = 'masternode'

        self.tn = ThreadedNode(
            node_type=node_type,
            constitution=self.create_constitution(node_type=node_type),
            raw_driver=self.driver,
            block_storage=self.block_storage,
            wallet=self.node_wallet
        )

        self.tn.start()
        self.async_sleep(2)

        self.assertIsNone(self.tn.err)
        self.assertIsInstance(self.tn.node, Masternode)

        while not self.tn.node_started:
            self.async_sleep(1)

        self.assertTrue(self.tn.node.started)

    def test_start__creates_started_delegate_instance_raises_no_errors(self):
        node_type = 'delegate'

        self.tn = ThreadedNode(
            node_type=node_type,
            constitution=self.create_constitution(node_type=node_type),
            raw_driver=self.driver,
            block_storage=self.block_storage,
            wallet=self.node_wallet
        )

        self.tn.start()
        self.async_sleep(2)

        self.assertIsNone(self.tn.err)
        self.assertIsInstance(self.tn.node, Delegate)

        while not self.tn.node_started:
            self.async_sleep(1)

        self.assertTrue(self.tn.node.started)

    def test_can_start_multiple_threaded_node_instances(self):
        wallet_mn = Wallet()
        mn_dir = Path(f'{self.node_dir}/{wallet_mn.verifying_key}')
        mn_state_dir = Path(f'{mn_dir}/state')
        mn_state_dir.mkdir(parents=True, exist_ok=True)

        wallet_del = Wallet()
        del_dir = Path(f'{self.node_dir}/{wallet_del.verifying_key}')
        del_state_dir = Path(f'{del_dir}/state')
        del_state_dir.mkdir(parents=True, exist_ok=True)

        constitution = {
            'masternodes': [wallet_mn.verifying_key],
            'delegates': [wallet_del.verifying_key]
        }

        masternode = ThreadedNode(
            node_type="masternode",
            constitution=constitution,
            raw_driver=ContractDriver(driver=FSDriver(root=Path(mn_state_dir))),
            block_storage=BlockStorage(home=Path(mn_dir)),
            wallet=wallet_mn
        )
        masternode.start()

        while not masternode.running:
            self.async_sleep(0.1)

        delegate = ThreadedNode(
            node_type="delegate",
            constitution=constitution,
            raw_driver=ContractDriver(driver=FSDriver(root=Path(del_state_dir))),
            block_storage=BlockStorage(home=Path(del_dir)),
            wallet=wallet_del,
            index=1
        )
        delegate.start()

        while not delegate.running:
            self.async_sleep(0.1)

        self.nodes.append(masternode)
        self.nodes.append(delegate)

        while not masternode.node_started or not delegate.node_started:
            self.async_sleep(1)

        self.assertTrue(masternode.node_started)
        self.assertTrue(delegate.node_started)

    def test_threaded_nodes_can_connect_as_peers(self):
        wallet_mn = Wallet()
        mn_dir = Path(f'{self.node_dir}/{wallet_mn.verifying_key}')
        mn_state_dir = Path(f'{mn_dir}/state')
        mn_state_dir.mkdir(parents=True, exist_ok=True)

        wallet_del = Wallet()
        del_dir = Path(f'{self.node_dir}/{wallet_del.verifying_key}')
        del_state_dir = Path(f'{del_dir}/state')
        del_state_dir.mkdir(parents=True, exist_ok=True)

        constitution = {
            'masternodes': [wallet_mn.verifying_key],
            'delegates': [wallet_del.verifying_key]
        }

        bootnodes = {
            wallet_mn.verifying_key: 'tcp://127.0.0.1:19000',
            wallet_del.verifying_key: 'tcp://127.0.0.1:19001'
        }

        masternode = ThreadedNode(
            node_type="masternode",
            constitution=constitution,
            bootnodes=bootnodes,
            raw_driver=ContractDriver(driver=FSDriver(root=Path(mn_state_dir))),
            block_storage=BlockStorage(home=Path(mn_dir)),
            wallet=wallet_mn
        )
        masternode.start()

        while not masternode.running:
            self.async_sleep(0.1)

        delegate = ThreadedNode(
            node_type="delegate",
            constitution=constitution,
            bootnodes=bootnodes,
            raw_driver=ContractDriver(driver=FSDriver(root=Path(del_state_dir))),
            block_storage=BlockStorage(home=Path(del_dir)),
            wallet=wallet_del,
            index=1
        )
        delegate.start()

        while not delegate.running:
            self.async_sleep(0.1)

        self.nodes.append(masternode)
        self.nodes.append(delegate)

        while not masternode.node_started or not delegate.node_started:
            self.async_sleep(1)

        self.assertTrue(masternode.node_started)
        self.assertTrue(delegate.node_started)

        self.async_sleep(10)

        for node in self.nodes:
            for peer in node.network.peer_list:
                connected = peer.is_connected
                self.assertTrue(peer.is_connected)

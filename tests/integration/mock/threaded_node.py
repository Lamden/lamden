from contracting.db.driver import ContractDriver, FSDriver, InMemDriver
from contracting.client import ContractingClient
from lamden.crypto.wallet import Wallet
from lamden.network import Network
from lamden.nodes.base import Node
from lamden.nodes.events import EventWriter
from lamden.nodes.filequeue import FileQueue
from lamden.storage import BlockStorage, NonceStorage
from pathlib import Path
from tests.integration.mock.mock_data_structures import MockBlocks
import asyncio
import inspect
import os
import shutil
import threading
import unittest

def create_a_node(index=0, node_wallet=Wallet(), bootnodes=None, genesis_block=None, temp_storage_root=None,
                  metering=False, network_await_connect_all_timeout=None):

    temp_storage_root = temp_storage_root if temp_storage_root is not None else Path().cwd().joinpath('temp_network')

    try:
        shutil.rmtree(temp_storage_root)
    except FileNotFoundError:
        pass
    temp_storage_root.mkdir(exist_ok=True, parents=True)

    node_dir = Path(f'{temp_storage_root}/{node_wallet.verifying_key}')

    raw_driver = FSDriver(node_dir)
    #raw_driver = InMemDriver()
    block_storage = BlockStorage(root=node_dir)
    nonce_storage = NonceStorage(root=node_dir)
    event_writer = EventWriter(root=node_dir)

    tx_queue = FileQueue(root=node_dir)

    bootnodes = bootnodes or {}

    return ThreadedNode(
        index=index,
        wallet=node_wallet,
        bootnodes=bootnodes,
        raw_driver=raw_driver,
        block_storage=block_storage,
        nonce_storage=nonce_storage,
        tx_queue=tx_queue,
        genesis_block=genesis_block,
        metering=metering,
        event_writer=event_writer,
        network_await_connect_all_timeout=network_await_connect_all_timeout
    )

class ThreadedNode(threading.Thread):
    def __init__(self,
                 block_storage: BlockStorage,
                 nonce_storage: NonceStorage,
                 raw_driver,
                 tx_queue: FileQueue = None,
                 index=0,
                 bootnodes={},
                 bypass_catchup=False,
                 metering=False,
                 wallet: Wallet = None,
                 reconnect_attempts=60,
                 genesis_block=None,
                 delay=None,
                 event_writer=None,
                 join=False,
                 network_await_connect_all_timeout=None):

        threading.Thread.__init__(self)

        self.daemon = True

        self.index = index
        self.bootnodes = bootnodes
        self.genesis_block = genesis_block

        self.raw_driver = raw_driver

        self.contract_driver = ContractDriver(driver=self.raw_driver)
        self.block_storage = block_storage
        self.nonces = nonce_storage

        self.class_path = os.path.abspath(inspect.getfile(self.__class__))
        self.client = ContractingClient(
            driver=self.contract_driver,
            submission_filename=os.path.dirname(self.class_path) + '/submission.py'
        )
        self.tx_queue = tx_queue if tx_queue is not None else FileQueue()
        self.event_writer = event_writer if event_writer is not None else EventWriter()

        self.bypass_catchup = bypass_catchup

        self.metering = metering

        self.wallet = wallet or Wallet()

        self.running = False
        self.loop = None
        self.node: Node = None
        self.join_network = join

        self.err = None

        self.reconnect_attempts = reconnect_attempts
        self.network_await_connect_all_timeout = network_await_connect_all_timeout
        self.delay = delay

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
    def current_hash(self) -> str:
        return self.node.get_current_hash()

    @property
    def current_height(self) -> int:
        return self.node.get_current_height()

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
        return self.node.get_last_processed_hlc()

    @property
    def blocks(self) -> BlockStorage:
        return self.node.blocks

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

            self.node = Node(
                bootnodes=self.bootnodes,
                wallet=self.wallet,
                socket_ports=self.create_socket_ports(index=self.index),
                driver=self.contract_driver,
                client=self.client,
                blocks=self.block_storage,
                genesis_block=self.genesis_block,
                tx_queue=self.tx_queue,
                reconnect_attempts=self.reconnect_attempts,
                testing=True,
                delay=self.delay,
                nonces=self.nonces,
                join=self.join_network,
                metering=self.metering,
                event_writer=self.event_writer,
            )

            self.node.network.set_to_local()
            if isinstance(self.network_await_connect_all_timeout, int):
                self.node.network.connect_to_all_peers_wait_sec = self.network_await_connect_all_timeout

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
        return self.raw_driver.get(item=key)

    def get_cached_smart_contract_value(self, key: str) -> any:
        key_split = key.split(".")
        contract = key_split.pop(0)

        key_split = key_split[0].split(":")
        variable = key_split.pop(0)

        arguments = key_split

        return self.node.driver.get_var(contract=contract, variable=variable, arguments=arguments)

    def get_latest_block(self) -> dict:
        return self.network.get_latest_block()

    def send_tx(self, encoded_tx: bytes):
        self.node.tx_queue.append(encoded_tx)

    def sleep(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.sleep(0.5))

    async def stop(self):
        if not self.node:
            return
        print('AWAITING NODE STOP')
        await self.node.stop()
        print('NODE STOP EXITED')

        self.running = False
        print(f'Threaded Node {self.index} Stopped.')

class TestThreadedNode(unittest.TestCase):
    def setUp(self):
        self.node_wallet = Wallet()

        self.current_path = Path.cwd()
        self.test_fixture_dir = self.current_path.joinpath('fixtures')

        if self.test_fixture_dir.is_dir():
            shutil.rmtree(self.test_fixture_dir)

        self.node_dir = self.test_fixture_dir.joinpath('nodes')

        self.driver = ContractDriver(driver=FSDriver(root=self.node_dir))
        self.block_storage = BlockStorage(root=self.node_dir)
        self.nonce_storage = NonceStorage(root=self.node_dir)

        self.blocks = MockBlocks(num_of_blocks=1, initial_members={'masternodes': [self.node_wallet.verifying_key]})

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

        if self.test_fixture_dir.is_dir():
            shutil.rmtree(self.test_fixture_dir)

    def stop_threaded_node(self, tn):
            task = asyncio.ensure_future(tn.stop())
            while not task.done():
                self.async_sleep(0.1)

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_threaded_node_instance__raises_no_errors(self):
        try:
            self.tn = ThreadedNode(
                raw_driver=self.driver,
                block_storage=self.block_storage,
                wallet=self.node_wallet,
                nonce_storage=self.nonce_storage,
                genesis_block=self.blocks.get_block_by_index(index=0)
            )
        except Exception as err:
            print(err)
            self.fail("Threaded Node should run and raise no exceptions.")

        self.assertIsInstance(self.tn, ThreadedNode)

    def test_start__creates_started_node_instance_raises_no_errors(self):
        self.tn = ThreadedNode(
            raw_driver=self.driver,
            block_storage=self.block_storage,
            wallet=self.node_wallet,
            nonce_storage=self.nonce_storage,
            genesis_block=self.blocks.get_block_by_index(index=0)
        )

        self.tn.start()
        self.async_sleep(2)

        self.assertIsNone(self.tn.err)
        self.assertIsInstance(self.tn.node, Node)

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

        self.blocks = MockBlocks(num_of_blocks=1, initial_members={'masternodes': [wallet_mn.verifying_key, wallet_del.verifying_key]})

        node_1 = ThreadedNode(
            raw_driver=ContractDriver(driver=FSDriver(root=Path(mn_state_dir))),
            block_storage=BlockStorage(root=Path(mn_dir)),
            wallet=wallet_mn,
            nonce_storage=NonceStorage(root=Path(mn_dir)),
            genesis_block=self.blocks.get_block_by_index(index=0)
        )
        node_1.start()

        while not node_1.running:
            self.async_sleep(0.1)

        node_2 = ThreadedNode(
            raw_driver=ContractDriver(driver=FSDriver(root=Path(del_state_dir))),
            block_storage=BlockStorage(root=Path(del_dir)),
            wallet=wallet_del,
            nonce_storage=NonceStorage(root=Path(del_dir)),
            genesis_block=self.blocks.get_block_by_index(index=0),
            index=1
        )
        node_2.start()

        while not node_2.running:
            self.async_sleep(0.1)

        self.nodes.append(node_1)
        self.nodes.append(node_2)

        while not node_1.node_started or not node_2.node_started:
            self.async_sleep(1)

        self.assertTrue(node_1.node_started)
        self.assertTrue(node_2.node_started)

    def test_threaded_nodes_can_connect_as_peers(self):
        wallet_mn = Wallet()
        mn_dir = Path(f'{self.node_dir}/{wallet_mn.verifying_key}')
        mn_state_dir = Path(f'{mn_dir}/state')
        mn_state_dir.mkdir(parents=True, exist_ok=True)

        wallet_del = Wallet()
        del_dir = Path(f'{self.node_dir}/{wallet_del.verifying_key}')
        del_state_dir = Path(f'{del_dir}/state')
        del_state_dir.mkdir(parents=True, exist_ok=True)

        bootnodes = {
            wallet_mn.verifying_key: 'tcp://127.0.0.1:19000',
            wallet_del.verifying_key: 'tcp://127.0.0.1:19001'
        }

        self.blocks = MockBlocks(num_of_blocks=1, initial_members={'masternodes': [wallet_mn.verifying_key, wallet_del.verifying_key]})

        masternode = ThreadedNode(
            bootnodes=bootnodes,
            raw_driver=ContractDriver(driver=FSDriver(root=Path(mn_state_dir))),
            block_storage=BlockStorage(root=Path(mn_dir)),
            nonce_storage=self.nonce_storage,
            genesis_block=self.blocks.get_block_by_index(index=0),
            wallet=wallet_mn
        )
        masternode.start()

        while not masternode.running:
            self.async_sleep(0.1)

        delegate = ThreadedNode(
            bootnodes=bootnodes,
            raw_driver=ContractDriver(driver=FSDriver(root=Path(del_state_dir))),
            block_storage=BlockStorage(root=Path(del_dir)),
            wallet=wallet_del,
            nonce_storage=self.nonce_storage,
            genesis_block=self.blocks.get_block_by_index(index=0),
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

        for node in self.nodes:
            for peer in node.network.peer_list:
                self.assertTrue(peer.is_connected)

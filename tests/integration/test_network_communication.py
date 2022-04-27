from lamden.new_network import Network, ACTION_GET_LATEST_BLOCK
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, FSDriver

from unittest import TestCase
from pathlib import Path
import shutil

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNetwork(TestCase):
    def setUp(self):
        self.current_path = Path.cwd()
        self.nodes_fixtures_dir = Path(f'{self.current_path}/fixtures/nodes')

        try:
            shutil.rmtree(self.nodes_fixtures_dir)
        except:
            pass

        self.networks = []
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        for network in self.networks:
            task = asyncio.ensure_future(network.stop())
            while not task.done():
                self.async_sleep(0.1)

        if not self.loop.is_closed():
            self.loop.stop()
            self.loop.close()

    def get_latest_block(self):
        return {}

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def set_smart_contract_keys(self):
        all_network_vks = self.all_network_vks()

        for network in self.networks:
            network.driver.driver.set(
                key="masternodes.S:members",
                value=all_network_vks
            )

    def all_network_vks(self) -> list:
       return [network.vk for network in self.networks]

    def create_network(self, index=0):
        network_wallet = Wallet()

        network_dir = Path(f'{self.current_path}/fixtures/nodes/{network_wallet.verifying_key}')
        network_dir.mkdir(parents=True, exist_ok=True)

        network = Network(
            wallet=Wallet(),
            socket_ports=self.create_socket_ports(index),
            driver=ContractDriver(driver=FSDriver(root=network_dir))
        )
        network.ip = '127.0.0.1'

        network.add_action(ACTION_GET_LATEST_BLOCK, self.get_latest_block)

        self.networks.append(network)

        self.set_smart_contract_keys()

        return network

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_start_one_local_network(self):
        network_1 = self.create_network(index=0)

        self.assertIsInstance(network_1, Network)

        network_1.start()
        while not network_1.is_running:
            self.async_sleep(0.1)

        self.assertTrue(network_1.is_running)

        print(self.networks[0].get_masternode_and_delegate_vk_list())

    def test_ten_networks_can_start_locally(self):
        num_of_networks = 10

        for i in range(num_of_networks):
            network = self.create_network(index=i)

            self.assertIsInstance(network, Network)

            network.start()
            while not network.is_running:
                self.async_sleep(0.1)

        self.assertEqual(num_of_networks, len(self.networks))


    def test_networks_can_add_each_other_as_peers(self):
        num_of_networks = 2

        for i in range(num_of_networks):
            network = self.create_network(index=i)

            self.assertIsInstance(network, Network)

            network.start()
            while not network.is_running:
                self.async_sleep(0.1)

        network_1 = self.networks[0]
        network_2 = self.networks[1]

        network_1.connect_peer(
            ip=network_2.local_address,
            vk=network_2.vk
        )

        peer_2 = network_1.get_peer(vk=network_2.vk)

        while not peer_2.is_verified:
            self.async_sleep(0.1)

        while network_2.num_of_peer() == 0:
            self.async_sleep(0.1)

        for network in self.networks:
            self.assertTrue(network.num_of_peers_connected == 1)





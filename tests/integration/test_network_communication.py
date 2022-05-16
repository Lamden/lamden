import zmq.asyncio

from lamden.network import Network, ACTION_GET_LATEST_BLOCK
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, FSDriver
from tests.unit.helpers.mock_request import MockRequest

from tests.integration.mock.threaded_network import ThreadedNetwork

from unittest import TestCase
from pathlib import Path
import shutil
import json
import time

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
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.main = True

    def tearDown(self):
        self.stop_threaded_networks()

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

    def set_smart_contract_keys_threaded(self):
        all_network_vks = self.all_network_vks()

        for network in self.networks:
            network.n.driver.driver.set(
                key="masternodes.S:members",
                value=all_network_vks
            )


    def all_network_vks(self) -> list:
       return [network.vk for network in self.networks]


    def create_threaded_network(self, index=0) -> Network:
        network_wallet = Wallet()

        network_dir = Path(f'{self.current_path}/fixtures/nodes/{network_wallet.verifying_key}')
        network_dir.mkdir(parents=True, exist_ok=True)

        network = ThreadedNetwork(
            wallet=Wallet(),
            socket_ports=self.create_socket_ports(index),
            driver=ContractDriver(driver=FSDriver(root=network_dir))
        )

        self.networks.append(network)

        self.set_smart_contract_keys()

        return network

    def stop_threaded_networks(self):
        tasks = []
        for network in self.networks:
            if network.is_running:
                task = asyncio.ensure_future(network.stop())
                while not task.done():
                    self.async_sleep(1)

                tasks.append(task)

        self.loop.run_until_complete(asyncio.gather(*tasks))

        for network in self.networks:
            network.join()


    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_start_one_threaded_network(self):
        '''
            One Threaded Netowrk can start up, no errors.
        '''
        network_1 = self.create_threaded_network(index=0)
        network_1.start()

        self.async_sleep(2)

        self.assertTrue(network_1.is_running)

    def test_two_threaded_networks_can_add_each_other_as_peers(self):
        '''
            Start up two networks, connet #1 to #2 and see that #2 adds in the process #1.
        '''
        num_of_networks = 2

        for i in range(num_of_networks):
            network = self.create_threaded_network(index=i)

            network.start()
            while not network.is_running:
                self.async_sleep(0.1)

        network_1 = self.networks[0]
        network_2 = self.networks[1]

        self.set_smart_contract_keys_threaded()

        network_2.n.router.refresh_cred_provider_vks(vk_list=self.all_network_vks())

        network_1.n.connect_peer(
            ip=network_2.n.local_address,
            vk=network_2.vk
        )

        self.async_sleep(1)

        peer_2 = network_1.n.get_peer(vk=network_2.vk)
        self.assertTrue(peer_2.is_verified)

        peer_1 = network_2.n.get_peer(vk=network_1.vk)
        self.assertTrue(peer_1.is_verified)

        for network in self.networks:
            num_of_peers_connected = network.n.num_of_peers_connected()
            self.assertEqual(1, num_of_peers_connected)

    def test_threaded_networks_can_discover_peers_via_new_connection_PubSub_from_one_network(self):
        '''
            network #1 connects manually to networks #2 and #3.
            networks #2 and #3 connect back to network #1 during that process.
            then networks #2 and #3 discover each other from network #1's pub socket and connect to each other.
        '''

        start_time = time.time()
        num_of_networks = 3

        for i in range(num_of_networks):
            network = self.create_threaded_network(index=i)

            network.start()
            while not network.is_running:
                self.async_sleep(0.1)

        done_starting = time.time()
        print(f'It took {done_starting - start_time} seconds to start all networks')

        network_1 = self.networks[0]
        network_2 = self.networks[1]
        network_3 = self.networks[2]

        self.set_smart_contract_keys_threaded()

        for network in self.networks:
            network.n.router.refresh_cred_provider_vks(vk_list=self.all_network_vks())

        # Connect network #1 to network #2
        network_1.n.connect_peer(
            ip=network_2.n.local_address,
            vk=network_2.vk
        )
        self.async_sleep(1)

        # Connect network #1 to network #3
        network_1.n.connect_peer(
            ip=network_3.n.local_address,
            vk=network_3.vk
        )

        # Wait for network discovery to happen
        self.async_sleep(1)

        # All networks end up with 2 peers due to discovery
        for network in self.networks:
            num_of_peers_connected = network.n.num_of_peers_connected()
            self.assertEqual(2, num_of_peers_connected)

    def test_threaded_networks_can_discover_peers_via_new_connection_PubSub_async_discovery(self):
        '''
            network #1 connects manually to network #2 and #2 then connects back to #1.
            network #2 connects manually to network #3 amd #3 then connects back to #2.
            networks #1 and #3 discover each other via PubSub.
        '''

        start_time = time.time()
        num_of_networks = 3

        for i in range(num_of_networks):
            network = self.create_threaded_network(index=i)

            network.start()
            while not network.is_running:
                self.async_sleep(0.1)

        done_starting = time.time()
        print(f'It took {done_starting - start_time} seconds to start all networks')

        network_1 = self.networks[0]
        network_2 = self.networks[1]
        network_3 = self.networks[2]

        self.set_smart_contract_keys_threaded()

        for network in self.networks:
            network.n.router.refresh_cred_provider_vks(vk_list=self.all_network_vks())

        # Connect network #1 to network #2
        network_1.n.connect_peer(
            ip=network_2.n.local_address,
            vk=network_2.vk
        )
        self.async_sleep(1)

        # Connect network #2 to network #3
        network_2.n.connect_peer(
            ip=network_3.n.local_address,
            vk=network_3.vk
        )

        # Wait for network discovery to happen
        self.async_sleep(5)

        # All networks end up with 2 peers due to discovery
        for network in self.networks:
            num_of_peers_connected = network.n.num_of_peers_connected()
            self.assertEqual(2, num_of_peers_connected)

    def test_threaded_networks_new_peer_joining_existing_network_can_get_all_peers_and_all_peer_discover_new_peer(self):
        '''
            Join 3 networks together.
            Create a 4th network and join it to network #1.
            Network #1 will join back to network #4 and publish the new connection to networks #2 and #3.
            Networks #2 and #3 will join to network #4 who will join back to them.
        '''

        num_of_networks = 3

        for i in range(num_of_networks):
            network = self.create_threaded_network(index=i)

            network.start()
            while not network.is_running:
                self.async_sleep(0.1)

            self.set_smart_contract_keys_threaded()
            for network in self.networks:
                network.n.router.refresh_cred_provider_vks(vk_list=self.all_network_vks())

            # Connect network #1 to this new network
            if i > 0:
                network_1 = self.networks[0]

                # Connect network #1 to network #2
                network_1.n.connect_peer(
                    ip=network.n.local_address,
                    vk=network.vk
                )
                self.async_sleep(1)

        # All networks end up with 2 peers due to discovery
        for network in self.networks:
            num_of_peers_connected = network.n.num_of_peers_connected()
            self.assertEqual(2, num_of_peers_connected)

        # Create and start network #4
        network_4 = self.create_threaded_network(index=3)
        network_4.start()

        while not network_4.is_running:
            self.async_sleep(0.1)

        # Update all keys
        self.set_smart_contract_keys_threaded()
        for network in self.networks:
            network.n.router.refresh_cred_provider_vks(vk_list=self.all_network_vks())

        # Connect network #4 to network #1
        network_1 = self.networks[0]
        network_4.n.connect_peer(
            ip=network_1.n.local_address,
            vk=network_1.vk
        )

        # Wait for network discovery to happen
        self.async_sleep(8)

        # All networks end up with 3 peers due to discovery
        for network in self.networks:
            num_of_peers_connected = network.n.num_of_peers_connected()
            self.assertEqual(3, num_of_peers_connected)
from cilantro_ee.constants import conf

from cilantro_ee.networking.network import Network
from cilantro_ee.core.block_fetch import BlockFetcher

from cilantro_ee.nodes.new_block_inbox import NBNInbox
from cilantro_ee.storage import VKBook
from cilantro_ee.sockets.socket_book import SocketBook
from cilantro_ee.contracts import sync
from cilantro_ee.networking.parameters import Parameters, ServiceType, NetworkParameters
import cilantro_ee
import zmq.asyncio
import asyncio

from cilantro_ee.storage.contract import BlockchainDriver

class Node:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, overwrite=False,
                 bootnodes=conf.BOOTNODES, network_parameters=NetworkParameters(), driver=BlockchainDriver()):
        # Seed state initially
        if driver.get_contract('vkbook') is None or overwrite:
            sync.extract_vk_args(constitution)
            sync.submit_vkbook(constitution, overwrite=overwrite)

        self.contacts = VKBook()

        self.parameters = Parameters(socket_base, ctx, wallet, contacts=self.contacts)

        # stuff
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx
        self.network_parameters = network_parameters

        self.bootnodes = bootnodes
        self.constitution = constitution
        self.overwrite = overwrite

        self.driver = driver

        self.block_fetcher = BlockFetcher(
            wallet=self.wallet,
            ctx=self.ctx,
            contacts=self.contacts,
            masternode_sockets=SocketBook(
                socket_base=self.socket_base,
                service_type=ServiceType.BLOCK_SERVER,
                phonebook_function=self.contacts.contract.get_masternodes,
                ctx=self.ctx
            )
        )

        self.network = Network(
            wallet=self.wallet,
            ctx=self.ctx,
            socket_base=socket_base,
            bootnodes=self.bootnodes,
            params=self.network_parameters,
            initial_del_quorum=self.contacts.delegate_quorum_min,
            initial_mn_quorum=self.contacts.masternode_quorum_min,
            mn_to_find=self.contacts.masternodes,
            del_to_find=self.contacts.delegates,
        )

        self.nbn_inbox = NBNInbox(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_NOTIFICATIONS,
                bind=True),
            ctx=self.ctx,
            driver=self.driver,
            contacts=self.contacts
        )

        self.running = False

    async def start(self):
        await self.network.start()

        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')

        # Catchup
        if len(self.contacts.masternodes) > 1:
            await self.block_fetcher.sync()

        self.running = True

        asyncio.ensure_future(self.nbn_inbox.serve())

    def stop(self):
        self.network.stop()
        self.nbn_inbox.stop()
        self.running = False
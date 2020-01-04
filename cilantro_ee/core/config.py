from cilantro_ee.crypto import Wallet
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.services.storage.master import CilantroStorageDriver
from cilantro_ee.networking.parameters import NetworkParameters
from contracting.client import ContractingClient

import zmq.asyncio


# Helper class that all services can share. Defined at the start of the software lifecycle
class SystemConfig:
    def __init__(self, wallet: Wallet, ctx: zmq.asyncio.Context, socket_base: str, contacts: VKBook,
                 client: ContractingClient, driver: MetaDataStorage, network_parameters: NetworkParameters,
                 blocks: CilantroStorageDriver=None):

        self.wallet = wallet
        self.ctx = ctx
        self.socket_base = socket_base
        self.contacts = contacts
        self.client = client
        self.driver = driver
        self.network_parameters = network_parameters
        self.blocks = blocks

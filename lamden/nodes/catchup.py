import asyncio
import threading

from lamden.logger.base import get_logger
from lamden import storage
from lamden.network import Network
from lamden.peer import Peer
from lamden.crypto.block_validator import verify_block

from contracting.db.driver import ContractDriver
from contracting.db.encoder import convert_dict

from random import choice


class CatchupHandler:
    def __init__(self, network: Network, contract_driver: ContractDriver, block_storage: storage.BlockStorage,
                 nonce_storage: storage.NonceStorage, hardcoded_peers: bool = False):
        self.current_thread = threading.current_thread()

        self.network = network
        self.block_storage = block_storage
        self.contract_driver = contract_driver
        self.nonce_storage = nonce_storage

        self.hardcoded_peers = hardcoded_peers

        self.catchup_peers = []
        self.valid_peers = [
            "11185fe3c6e68d11f89929e2f531de3fb640771de1aee32c606c30c70b6600d2",
            "a04b5891ef8cd27095373a4f75b899ec2bc0883c02e506a6a5b55b491998cc3f",
            "b09493df6c18d17cc883ebce54fcb1f5afbd507533417fe32c006009a9c3c4a",
            "ffd7182fcfd0d84ca68845fb11bafad11abca2f9aca8754a6d9cad7baa39d28b",
            "9d2dbfcc8cd20c8e41b24db367f215e4ac527dc6a2a0acdb4b6008d13d043ef8",
            "e79133b02cd2a84e2ce5d24b2f44433f61f0db7e10acedfc241e94dff06f710a"
        ]

        self.log = get_logger(f'[{self.current_thread.name}][CATCHUP HANDLER]')

    @property
    def latest_block_number(self):
        return storage.get_latest_block_height(self.contract_driver)

    async def run(self):
        # Get the current latest block stored and the latest block of the network
        self.log.info('Running catchup.')

        self.catchup_peers = self.network.get_all_connected_peers()

        if self.hardcoded_peers:
            self.catchup_peers = [peer for peer in self.catchup_peers if peer.server_vk in self.valid_peers]

        if len(self.catchup_peers) == 0:
            #raise ValueError(f'No peers available for catchup!')
            self.log.error('No peers available for catchup!')
        else:
            #!# Validate this block
            highest_network_block = await self.get_highest_network_block()

            if highest_network_block is None:
                self.log.info('Network is still at genesis.')
                return 'not_run'

            highest_block_number = highest_network_block.get('number')
            my_current_height = self.latest_block_number

            if my_current_height >= int(highest_block_number):
                self.log.info('At latest block height, catchup not needed.')
                return 'not_run'

            self.process_block(block=highest_network_block)
            self.update_block_db(block=highest_network_block)

            current_block_number = highest_block_number
            while True:
                # get the previous block
                block = await self.get_previous_block(block_num=current_block_number)

                if block is None:
                    break

                block_num = int(block.get('number'))

                if block_num == 0:
                    self.log.info('Genesis Block Reached.')
                    break

                if block_num == my_current_height:
                    self.log.info('Caught Up to latest.')
                    break

                self.process_block(block=block)

                current_block_number = block.get('number')

                await asyncio.sleep(0.05)

        self.network.refresh_approved_peers_in_cred_provider()
        self.log.warning('Catchup Complete!')

    async def get_highest_network_block(self) -> dict:
        highest_block_num = self.network.get_highest_peer_block()
        if highest_block_num > 0:
            block = await self.source_block_from_peers(block_num=highest_block_num, fetch_type='specific')
            return block

        return None

    async def get_previous_block(self, block_num: str) -> dict:
        return await self.source_block_from_peers(block_num=int(block_num), fetch_type='previous')

    async def source_block_from_peers(self, block_num: int, fetch_type: str) -> dict:
        catch_peers_vk_list = [peer.server_vk for peer in self.catchup_peers]

        while len(catch_peers_vk_list) > 0:
            random_peer = self.get_random_catchup_peer(vk_list=catch_peers_vk_list)
            peer_vk = random_peer.server_vk

            if fetch_type == 'previous':
                res = await random_peer.get_previous_block(block_num=block_num)
            elif fetch_type == 'specific':
                res = await random_peer.get_block(block_num=block_num)

            try:
                block = res['block_info']
                block_num = block.get('number')

                # If this is the genesis block then return it
                # OR if the block is valid, return it.
                if int(block_num) == 0 or verify_block(block):
                    return block

                raise ValueError(f'[{fetch_type}:{block_num}] {block.get("number")} from {peer_vk}')

            except Exception as err:
                self.log.error(err)
                self.log.error(f'[{fetch_type}:{block_num}] Could not get {fetch_type} block {block_num} from peer {peer_vk} during catchup.')

                catch_peers_vk_list.remove(peer_vk)

        raise ConnectionError("All catchup peers are offline.")

    def get_random_catchup_peer(self, vk_list) -> Peer:
        if len(vk_list) == 0:
            return None

        vk = choice(vk_list)
        return self.network.get_peer(vk=vk)

    def process_block(self, block: dict) -> None:
        block_num = block.get('number')
        has_block = self.block_storage.get_block(v=int(block_num))

        if has_block:
            return

        # Safe set the state changes (don't overwrite changes if they were set later blocks)
        self.safe_set_state_changes_and_rewards(block=block)

        # Save Nonce information
        self.save_nonce_information(block=block)

        # Store block in storage
        self.block_storage.store_block(block=block)

        self.log.info(f'Added block {block_num} from catchup.')

    def update_block_db(self, block: dict) -> None:
        self.contract_driver.driver.set(storage.LATEST_BLOCK_HASH_KEY, block['hash'])
        self.contract_driver.driver.set(storage.LATEST_BLOCK_HEIGHT_KEY, block['number'])

    def safe_set_state_changes_and_rewards(self, block: dict) -> None:
        state_changes = block['processed'].get('state', [])
        rewards = block.get('rewards', [])

        block_num = block.get('number')

        for s in state_changes:
            value = s['value']
            if type(value) is dict:
                value = convert_dict(value)

            self.contract_driver.driver.safe_set(
                key=s['key'],
                value=value,
                block_num=block_num
            )

        for s in rewards:
            value = s['value']
            if type(value) is dict:
                value = convert_dict(value)

            self.contract_driver.driver.safe_set(
                key=s['key'],
                value=value,
                block_num=block_num
            )

    def save_nonce_information(self, block: dict) -> None:
        payload = block['processed']['transaction']['payload']

        self.nonce_storage.safe_set_nonce(
            sender=payload['sender'],
            processor=payload['processor'],
            value=payload['nonce']
        )

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
        self.safe_block_num = -1

        self.catchup_peers = []
        self.valid_peers = [
            "11185fe3c6e68d11f89929e2f531de3fb640771de1aee32c606c30c70b6600d2",
            "a04b5891ef8cd27095373a4f75b899ec2bc0883c02e506a6a5b55b491998cc3f",
            "5b09493df6c18d17cc883ebce54fcb1f5afbd507533417fe32c006009a9c3c4a",
            "ffd7182fcfd0d84ca68845fb11bafad11abca2f9aca8754a6d9cad7baa39d28b",
            "9d2dbfcc8cd20c8e41b24db367f215e4ac527dc6a2a0acdb4b6008d13d043ef8",
            "e79133b02cd2a84e2ce5d24b2f44433f61f0db7e10acedfc241e94dff06f710a"
        ]

        self.log = get_logger(f'[{self.current_thread.name}][CATCHUP HANDLER]')

    @property
    def latest_block_number(self):
        return self.block_storage.get_latest_block_number() or 0

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

            latest_network_block = await self.source_block_from_peers(
                fetch_type='specific',
                block_num=highest_block_number
            )

            self.process_block(block=latest_network_block)

            current_block_number = latest_network_block.get('number')
            current_block_previous = latest_network_block.get('previous')
            while True:
                # get the previous block
                block = await self.get_previous_block(block_num=current_block_number)

                if block is None:
                    break

                block_num = int(block.get('number'))

                if block_num == 0:
                    self.log.info('Genesis Block Reached.')
                    break

                if block.get('hash') != current_block_previous:
                    self.log.error('Block chain breakdown. Hash mismatch. Exiting catchup.')
                    break

                if block_num == my_current_height:
                    self.log.info('Caught Up to latest.')
                    break

                self.process_block(block=block)

                current_block_number = block.get('number')
                current_block_previous = block.get('previous')

                await asyncio.sleep(0.05)

        self.network.refresh_approved_peers_in_cred_provider()
        self.log.warning('Catchup Complete!')

    async def get_highest_network_block(self) -> dict:
        block = await self.source_block_from_peers(fetch_type='latest')
        if block is None:
            return {
                'number': -1
            }

        return block

    async def get_previous_block(self, block_num: str) -> dict:
        return await self.source_block_from_peers(block_num=int(block_num), fetch_type='previous')

    async def source_block_from_peers(self, fetch_type: str, block_num: int = 0) -> dict:
        block_counts = {}
        consensus_reached = False
        consensus_block = None
        timeout = 5  # Set a reasonable timeout

        while len(self.catchup_peers) > 0 and not consensus_reached:
            tasks = []
            for peer in self.catchup_peers:
                if fetch_type == 'previous':
                    task = asyncio.ensure_future(peer.get_previous_block(block_num=block_num))
                elif fetch_type == 'specific':
                    task = asyncio.ensure_future(peer.get_block(block_num=block_num))
                elif fetch_type == 'latest':
                    task = asyncio.ensure_future(peer.get_latest_block_info())
                task.__peer__ = peer  # attach the peer directly to the task
                tasks.append(task)

            responses, _ = await asyncio.wait(tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)

            for future in responses:
                try:
                    res = future.result()
                    res_block = res['block_info']
                    res_block_num = res_block.get('number')
                    res_block_hash = res_block.get('hash')

                    if int(res_block_num) != 0 and fetch_type != 'latest':
                        old_block = int(res_block_num) <= self.safe_block_num
                        verify_block(block=res_block, old_block=old_block)

                    block_counts[res_block_hash] = block_counts.get(res_block_hash, 0) + 1
                    if block_counts[res_block_hash] / len(self.catchup_peers) > 0.51:
                        consensus_reached = True
                        consensus_block = res_block
                except Exception as err:
                    self.log.error(err)
                    peer = future.__peer__
                    self.catchup_peers.remove(peer)  # remove the unresponsive peer

        if consensus_reached:
            return consensus_block
        else:
            if len(self.catchup_peers) == 0:
                raise ValueError('No peers available for catchup!')

            return None

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

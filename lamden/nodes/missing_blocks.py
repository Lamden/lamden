from lamden import storage
from contracting.db.encoder import convert_dict, encode
from copy import deepcopy
from lamden.crypto.block_validator import verify_block
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver
from lamden.network import Network
from lamden.crypto.canonical import block_hash_from_block
from lamden.nodes.events import Event, EventWriter
from lamden.logger.base import get_logger
from lamden.peer import Peer

from random import choice
import os
import json
import asyncio
import threading

NEW_BLOCK_REORG_EVENT = 'block_reorg'


class MissingBlocksHandler:
    def __init__(self, block_storage: storage.BlockStorage, nonce_storage: storage.NonceStorage,
                 contract_driver: ContractDriver, network: Network, wallet: Wallet, event_writer: EventWriter,
                 root=None):
        if root is None:
            root = os.path.expanduser(".lamden")
        self.root = os.path.abspath(root)

        self.current_thread = threading.current_thread()

        self.missing_blocks_dir = os.path.join(self.root, "missing")
        self._init_missing_blocks_dir()

        self.block_storage = block_storage
        self.nonce_storage = nonce_storage
        self.contract_driver = contract_driver
        self.network = network
        self.event_writer = event_writer
        self.wallet = wallet

        self.log = get_logger(f'[{self.current_thread.name}][MISSING BLOCKS HANDLER]')

    def _init_missing_blocks_dir(self):
        if not os.path.exists(self.missing_blocks_dir):
            os.makedirs(self.missing_blocks_dir)

    def _read_missing_blocks_file(self):
        missing_blocks_file_path = os.path.join(self.missing_blocks_dir, "missing_blocks.json")
        try:
            with open(missing_blocks_file_path, 'r') as f:
                content = f.read()
                return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _validate_missing_blocks_data(self, data) -> bool:
        if data is None:
            return False

        if not isinstance(data, list) or not data:
            return False

        for item in data:
            if not isinstance(item, str):
                return False

        return True

    def _delete_missing_blocks_file(self):
        missing_blocks_file_path = os.path.join(self.missing_blocks_dir, "missing_blocks.json")
        try:
            os.remove(missing_blocks_file_path)
        except FileNotFoundError:
            pass

    async def _source_block_from_peers(self, block_num: int) -> dict:
        if not int(block_num) > 0:
            raise ValueError('cannot source genesis_block')

        peer_list = self.network.get_all_connected_peers()
        peers_vk_list = [peer.server_vk for peer in peer_list]

        while len(peers_vk_list) > 0:
            random_peer: Peer = self._get_random_catchup_peer(vk_list=peers_vk_list)
            peer_vk = random_peer.server_vk

            res = await random_peer.get_block(block_num=block_num)

            try:
                block = res['block_info']
                block_num = block.get('number')

                # If this is the genesis block then return it
                # OR if the block is valid, return it.
                if int(block_num) == 0 or verify_block(block):
                    return block

                raise ValueError(f'{block.get("number")} from {peer_vk}')

            except Exception as err:
                self.log.error(err)
                self.log.error(f'[{block_num}] Could not get block {block_num} from peer {peer_vk} during missing block processing.')

                peers_vk_list.remove(peer_vk)

        return None

    def _safe_set_state_changes_and_rewards(self, block: dict) -> None:
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

    def _save_nonce_information(self, block: dict) -> None:
        payload = block['processed']['transaction']['payload']

        self.nonce_storage.safe_set_nonce(
            sender=payload['sender'],
            processor=payload['processor'],
            value=payload['nonce']
        )

    def _write_reorg_event(self, block: dict):
        encoded_block = encode(block)
        e = Event(
            topics=[NEW_BLOCK_REORG_EVENT],
            data=encoded_block
        )
        try:
            self.event_writer.write_event(e)
            self.log.info(f'Successfully sent {NEW_BLOCK_REORG_EVENT} event: {e.__dict__}')
        except Exception as err:
            self.log.error(f'Failed to write {NEW_BLOCK_REORG_EVENT} event: {err}')

    def _get_random_catchup_peer(self, vk_list) -> Peer:
        if len(vk_list) == 0:
            return None

        vk = choice(vk_list)
        return self.network.get_peer(vk=vk)

    async def run(self):
        missing_block_numbers_list = self.get_missing_blocks_list()

        if len(missing_block_numbers_list) > 0:
            self.log.warning("Processing Missing Blocks.")
            self.process_missing_blocks(blocks=missing_block_numbers_list)

            self.recalc_block_hashes(starting_block_num=missing_block_numbers_list[0])
            self.log.warning("Finished Processing Missing Blocks.")


    def get_missing_blocks_list(self) -> list:
        data = self._read_missing_blocks_file()
        is_valid = self._validate_missing_blocks_data(data)

        if not is_valid:
            self._delete_missing_blocks_file()
            return []

        self._delete_missing_blocks_file()

        data.sort()
        return data

    async def process_missing_blocks(self, missing_block_numbers_list: list = None):
        for block_num in missing_block_numbers_list:
            block = await self._source_block_from_peers(block_num=int(block_num))
            if block is not None:
                self.process_block(block=block)

    def process_block(self, block):
        block_num: str = block.get('number')
        storage_block = self.block_storage.get_block(v=block_num)

        if storage_block:
            return 'already_exists'

        # Safe set the state changes (don't overwrite changes if they were set later blocks)
        self._safe_set_state_changes_and_rewards(block=block)

        # Save Nonce information
        self._save_nonce_information(block=block)

        # Store block in storage
        self.block_storage.store_block(block=block)

        self.log.info(f'Processed missing block {block_num}.')

    async def recalc_block_hashes(self, starting_block_number: str):
        self.log.warning("Starting to recalculate block hashes.")

        starting_block = self.block_storage.get_block(v=starting_block_number)

        # start with the block passed in
        current_block = starting_block

        while True:
            current_block_number = current_block.get('number')
            current_block_hash = current_block.get('hash')

            next_block = self.block_storage.get_next_block(v=int(current_block_number))

            if next_block is None:
                break

            next_block_number = next_block.get('number')
            next_block_previous_hash = next_block.get('previous')

            # only make changes if the previous hash is incorrect
            if next_block_previous_hash != current_block_hash:
                # change the hash in the next block
                next_block['previous'] = current_block_hash

                new_block_hash = block_hash_from_block(
                    hlc_timestamp=next_block.get('hlc_timestamp'),
                    block_number=next_block_number,
                    previous_block_hash=next_block.get('previous')

                )
                next_block['hash'] = new_block_hash
                # recalc the block hash including this new "previous hash"

                next_block.pop('minted')

                # resign the block to show we validated and minted it
                signature = self.wallet.sign(encode(deepcopy(next_block)))
                next_block['minted'] = {
                    'minter': self.wallet.verifying_key,
                    'signature': signature
                }

                # Delete the block currently in storage
                self.block_storage.remove_block(v=next_block_number)

                # Store the new corrected version
                self.block_storage.store_block(block=next_block)

                # Sent reorg event
                self._write_reorg_event(block=next_block)

                self.log.info(f'Recalculated block hash for block number {next_block_number}.')

            current_block = next_block

            await asyncio.sleep(0.05)

        self.log.info("Done recalculating block hashes.")



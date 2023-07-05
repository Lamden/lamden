from lamden import storage
from contracting.db.encoder import convert_dict
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver
from lamden.nodes.events import Event, EventWriter
from lamden.logger.base import get_logger

import time
import threading

ROLLBACK_EVENT = 'rollback'


class RollbackBlocksHandler:
    def __init__(self, block_storage: storage.BlockStorage, nonce_storage: storage.NonceStorage,
                 contract_driver: ContractDriver, wallet: Wallet, event_writer: EventWriter):

        self.current_thread = threading.current_thread()

        self.block_storage = block_storage
        self.nonce_storage = nonce_storage
        self.contract_driver = contract_driver
        self.event_writer = event_writer
        self.wallet = wallet

        self.log = get_logger(f'[{self.current_thread.name}][ROLLBACK BLOCKS HANDLER]')

    def _safe_set_state_changes_and_rewards(self, block: dict) -> None:
        if self.block_storage.is_genesis_block(block):
            state_changes = block['genesis']
            rewards = []
        else:
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
        if self.block_storage.is_genesis_block(block):
            return

        payload = block['processed']['transaction']['payload']

        self.nonce_storage.safe_set_nonce(
            sender=payload['sender'],
            processor=payload['processor'],
            value=payload['nonce']
        )

    def _write_rollback_event(self, rollback_point: str):
        e = Event(
            topics=[ROLLBACK_EVENT],
            data={rollback_point}
        )

        try:
            self.event_writer.write_event(e)
            self.log.info(f'Successfully sent {ROLLBACK_EVENT} event: {e.__dict__}')
        except Exception as err:
            self.log.error(f'Failed to write {ROLLBACK_EVENT} event: {err}')

    def _validate_rollback_point(self, rollback_point: str) -> bool:
        if rollback_point is None:
            return False

        try:
            int(rollback_point)
        except ValueError:
            return False

        if int(rollback_point) < 0:
            rollback_point = "0"

        return rollback_point

    def run(self, rollback_point: str = None):
        rollback_point = self._validate_rollback_point(rollback_point=rollback_point)

        if rollback_point == False:
            return
        self.log.warning(f'Rolling back to block {rollback_point}. This could take a while.')

        self.log.info(f'Deleting blocks greater than {rollback_point}...')
        self.delete_greater_blocks(rollback_point=rollback_point)

        self.log.info(f'Purging Current State...')
        self.purge_current_state()

        self.log.info(f'Processing Genesis Block State into Current State...')
        self.process_genesis_block()

        self.log.info(f'Building Current State from block {rollback_point} to 0...')
        self.process_all_blocks()

        self.log.warning(f'Rollback to block {rollback_point} complete!')

    def delete_greater_blocks(self, rollback_point: str = None):
        if rollback_point is None:
            return

        latest_block = self.block_storage.get_latest_block()

        while int(latest_block.get('number')) > int(rollback_point):
            self.block_storage.remove_block(latest_block.get('number'))
            latest_block = self.block_storage.get_latest_block()

    def purge_current_state(self):
        self.contract_driver.flush()
        self.nonce_storage.flush()

    def process_genesis_block(self) -> bool:
        genesis_block = self.block_storage.get_block(v=0)

        if genesis_block is None:
            return

        self._safe_set_state_changes_and_rewards(block=genesis_block)

    def process_all_blocks(self):
        current_block = self.block_storage.get_latest_block()
        last_print_time = time.time()

        while self.block_storage.is_genesis_block(current_block) is False:
            current_block_num = current_block.get('number')

            # Check if it has been more than 60 seconds since last print
            if time.time() - last_print_time >= 30:
                print(f"Still working... currently on block number: {current_block_num}")
                last_print_time = time.time()  # update last print time

            self._safe_set_state_changes_and_rewards(block=current_block)
            self._save_nonce_information(block=current_block)

            current_block = self.block_storage.get_previous_block(v=int(current_block_num))
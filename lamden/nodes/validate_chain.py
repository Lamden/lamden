from lamden.storage import BlockStorage
from contracting.db.driver import ContractDriver
from lamden.logger.base import get_logger
from lamden.crypto.block_validator import verify_block

import threading

VALIDATION_HEIGHT = '__validation_height'

class ValidateChainHandler:
    def __init__(self, block_storage: BlockStorage, contract_driver: ContractDriver):
        self.block_storage = block_storage
        self.contract_driver = contract_driver

        self.safe_block_num = -1

        self.current_thread = threading.current_thread()
        self.log = get_logger(f'[{self.current_thread.name}][VALIDATE CHAIN]')

    def set_validation_height(self, block_num: str):
        if not isinstance(block_num, str):
            return

        self.contract_driver.driver.set(VALIDATION_HEIGHT, block_num)

    def get_validation_height(self):
        validation_height = self.contract_driver.driver.get(VALIDATION_HEIGHT)

        if validation_height is None:
            return -1

        return validation_height

    def run(self):
        # Read block by block
        # Run validate, check previous hash
        # Log history

        current_validation_height = self.get_validation_height()

        if current_validation_height < 0:
            # Purge history as we will recreate it
            self.block_storage.member_history.purge()
            self.process_genesis_block()
            self.set_validation_height(block_num=0)
            current_validation_height = 0

        self.process_all_blocks(starting_block_num=current_validation_height)

    def process_genesis_block(self):
        block = self.block_storage.get_block(v=0)

        if block is not None:
            # self.validate_block(block=block)
            self.save_member_history(block=block)

    def process_all_blocks(self, starting_block_num: int):
        previous_block = self.block_storage.get_block(v=starting_block_num)
        block = self.block_storage.get_next_block(v=starting_block_num)

        while block is not None:
            block_num = block.get('number')

            # Validate current block signatures and proofs
            self.validate_block(block=block)
            self.validate_previous_hash(block=block, previous_block=previous_block)
            self.validate_consensus(block=block)
            self.save_member_history(block=block)
            self.set_validation_height(block_num=block_num)

            # Validate new block's previous hash
            next_block = self.block_storage.get_next_block(v=int(block_num))

            if next_block is not None:
                next_block_previous_hash = next_block.get('previous')

                assert block.get('hash') == next_block_previous_hash, f'BLOCK CHAIN BROKEN: {next_block.get("number")} has bad previous hash.'

            previous_block = block
            block = next_block


    def validate_block(self, block: dict) -> None:
        block_num = block.get("number")
        old_block = int(block_num) <= self.safe_block_num

        valid = verify_block(block=block, old_block=old_block)

        assert valid, f"block number {block_num} did not pass block validation."

    def validate_previous_hash(self, block: dict, previous_block: dict) -> None:
        previous_block_hash = previous_block.get('hash')
        previous_hash = block.get('previous')

        assert previous_block_hash == previous_hash, \
            f"Block Chain Broken: {block.get('number')} does not have correct previous hash."

    def validate_consensus(self, block: dict) -> None:
        block_num = block.get('number')
        proofs = block.get('proofs')

        for proof in proofs:
            vk = proof.get('signer')
            assert self.block_storage.is_member_at_block_height(block_num=block_num, vk=vk), f"block number {block_num} did not pass block consensus."

    def save_member_history(self, block: dict) -> None:
        if self.block_storage.is_genesis_block(block=block):
            state_changes = block.get('genesis')
        else:
            state_changes = block['processed'].get('state')

        for state_change in state_changes:
            if state_change.get('key') == 'masternodes.S:members':
                block_num = block.get('number')
                self.block_storage.member_history.set(block_num=block_num, members_list=state_change.get('value'))

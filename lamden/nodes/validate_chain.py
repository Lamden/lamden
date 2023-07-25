from lamden.storage import BlockStorage
from lamden.logger.base import get_logger
from lamden.crypto.block_validator import verify_block

import threading

class ValidateChainHandler:
    def __init__(self, block_storage: BlockStorage):
        self.block_storage = block_storage

        self.safe_block_num = -1

        self.current_thread = threading.current_thread()
        self.log = get_logger(f'[{self.current_thread.name}][VALIDATE CHAIN]')

    def run(self):
        # Read block by block
        # Run validate, check previous hash
        # Log history

        # Purge history as we will recreate it
        self.block_storage.member_history.purge()

        self.process_genesis_block()

        self.process_all_blocks()

    def process_genesis_block(self):
        block = self.block_storage.get_block(v=0)

        self.validate_block(block=block)

        if block is not None:
            self.save_member_history(block=block)

    def process_all_blocks(self):
        block = self.block_storage.get_next_block(v=0)

        while block is not None:
            block_num = block.get('number')

            # Validate current block signatures and proofs
            self.validate_block(block=block)
            self.validate_consensus(block=block)
            self.save_member_history(block=block)

            # Validate new block's previous hash
            next_block = self.block_storage.get_next_block(v=int(block_num))

            if next_block is not None:
                next_block_previous_hash = next_block.get('previous')

                assert block.get('hash') == next_block_previous_hash, f'BLOCK CHAIN BROKEN: {next_block.get("number")} has bad previous hash.'

            block = next_block

    def validate_block(self, block: dict) -> None:
        block_num = block.get("number")
        old_block = int(block_num) <= self.safe_block_num

        valid = verify_block(block=block, old_block=old_block)

        assert valid, f"block number {block_num} did not pass block validation."

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

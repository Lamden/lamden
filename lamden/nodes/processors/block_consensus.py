import threading
from collections import defaultdict
from lamden.storage import BlockStorage
from lamden.nodes.events import EventWriter, Event

from lamden.logger.base import get_logger

class BlockConsensus:
    def __init__(self, block_storage: BlockStorage, event_writer: EventWriter = None):
        self.block_storage = block_storage
        self.event_writer = event_writer

        self.member_counts = {}  # Initial member count at block number 0
        self.validation_height = 0
        self.pending_blocks = defaultdict(list)  # Block data received from the network
        self.minted_blocks = {}  # Block data minted by our node


        self.current_thread = threading.current_thread()
        self.log = get_logger(f'[{self.current_thread.name}][BLOCK CONSENSUS]')

    def _get_required_consensus(self, block_num: int):
        self._populate_member_count(block_num=block_num)
        member_count = self.member_counts[block_num]

        return member_count // 2 + 1

    def _cleanup(self) -> None:
        # Clean up block data and member counts that are no longer needed
        heights_to_remove = [h for h in self.pending_blocks if h <= self.validation_height]
        for h in heights_to_remove:
            del self.pending_blocks[h]
        heights_to_remove = [h for h in self.minted_blocks if h <= self.validation_height]
        for h in heights_to_remove:
            del self.minted_blocks[h]
        heights_to_remove = [h for h in self.member_counts if h <= self.validation_height]
        for h in heights_to_remove:
            del self.member_counts[h]

    def _populate_member_count(self, block_num: int):
        if self.member_counts.get(block_num) is None:
            members_list = self.block_storage.member_history.get(block_num=str(block_num))
            self.member_counts[block_num] = len(members_list)

    def _validate_block(self, block_num: int, block_hash: str):
        self.log.debug(self.pending_blocks)
        self.log.debug(self.minted_blocks)
        self.log.debug(self.member_counts)

        if block_num <= self.validation_height:
            # return is for testing
            return 'earlier'

        if self.pending_blocks[block_num].count(block_hash) >= self._get_required_consensus(block_num):
            self.log.warning("Attempting Consensus Check")
            if block_hash != self.minted_blocks.get(block_num):
                self.log.error(f"Block {block_num} failed to validate, possible node out of sync")
                self._cleanup()

                self.__send_event(event=Event(
                    topics=['out_of_sync'],
                    data={
                    'block_num': block_num,
                    'block_hash': block_hash
                }))

                return False
            else:
                self.log.info(f"Block {block_num} validated successfully")

                self.validation_height = block_num
                self._cleanup()

                self.__send_event(event=Event(
                    topics=['confirmed_block'],
                    data={
                    'block_num': block_num,
                    'block_hash': block_hash
                }))

                return True

    def __send_event(self, event: Event):
        if self.event_writer:
            self.event_writer.write_event(event)

    async def process_message(self, msg: dict) -> None:
        self.log.debug(f'process_message: {msg}')
        block_num = int(msg.get('block_num'))
        block_hash = msg.get('block_hash')

        # not needed at this point but available
        # node_vk = msg.get('vk')

        if block_num <= self.validation_height:
            return

        self.pending_blocks[block_num].append(block_hash)
        self._validate_block(block_num, block_hash)

    def post_minted_block(self, block: dict) -> None:
        self.log.debug(f'post_minted_block: {block}')
        block_num = int(block.get('number'))
        block_hash = block.get('hash')

        self.minted_blocks[block_num] = block_hash
        self.pending_blocks[block_num].append(block_hash)
        self._validate_block(block_num, block_hash)


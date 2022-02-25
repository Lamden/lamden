from lamden.logger.base import get_logger

NEW_BLOCK_EVENT = 'new_block'
from lamden.nodes.events import Event, EventWriter
from contracting.db.encoder import encode

import json

class CatchupProcessor():
    def __init__(self, apply_state_changes_from_block, blocks, update_block_db):
        self.log = get_logger('Catchup Inbox')

        self.apply_state_changes_from_block = apply_state_changes_from_block
        self.blocks = blocks
        self.update_block_db = update_block_db

        self.event_writer = EventWriter()

    def process_message(self, msg):
        new_block = msg.get("block_info")
        self.log.info(msg)
        self.log.info(new_block)

        # Apply state to DB
        self.apply_state_changes_from_block(block=new_block)

        # Store the block in the block db
        encoded_block = encode(new_block)
        encoded_block = json.loads(encoded_block)

        self.blocks.store_block(block=encoded_block)

        # Set the current block hash and height
        self.update_block_db(block=encoded_block)

        # create New Block Event
        self.event_writer.write_event(Event(
            topics=[NEW_BLOCK_EVENT],
            data=encoded_block
        ))


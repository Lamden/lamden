from cilantro_ee.protocol.comm.services import AsyncInbox, SocketStruct, Protocols
from cilantro_ee.messages import capnp as schemas
from cilantro_ee.storage.master import CilantroStorageDriver
from cilantro_ee.core.top import TopBlockManager
import os
import capnp

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')

BLOCK_DATA_REQUEST = 1
BLOCK_INDEX_REQUEST = 2
BLOCK_TOP_NUM = 3
BLOCK_TOP_HASH = 4


def block_dictionary_to_block_struct(block_dict):
    if '_id' in block_dict:
        del block_dict['_id']

    '''
    struct BlockData {
        blockHash @0 :Data;
        blockNum @1 :UInt32;
        blockOwners @2 :List(Text);
        prevBlockHash @3 :Data;
        subBlocks @4 :List(SB.SubBlock);
    }
    '''

    block = blockdata_capnp.BlockData.new_message()

    block.blockHash = block_dict['blockHash']
    block.blockNum = block_dict['blockNum']
    block.blockOwners = block_dict['blockOwners']
    block.prevBlockHash = block_dict['prevBlockHash']
    block.subBlocks = [subblock_capnp.SubBlock.from_bytes_packed(s).as_builder() for s in block_dict['subBlocks']]

    return block


def block_struct_to_block_dictionary(block_struct: blockdata_capnp.BlockData):
    block_dict = {
        'blockHash': block_struct.blockHash,
        'blockNum': block_struct.blockNum,
        'blockOwners': [owner for owner in block_struct.blockOwners],
        'prevBlockHash': block_struct.prevBlockHash,
        'subBlocks': [sb.copy().to_bytes_packed() for sb in block_struct.subBlocks]
    }

    return block_dict


# Provide a block driver to enable data and index requests
# Otherwise, this will just return latest num and hash, which both delegates and masters can do
class BlockServer(AsyncInbox):
    def __init__(self, driver=None, top=TopBlockManager()):
        self.driver = driver
        self.top = top
        super().__init__()

    async def handle_msg(self, _id, msg):
        msg_type, msg_blob = msg

        if msg_type == BLOCK_DATA_REQUEST and self.driver is not None:
            block_dict = await self.driver.get_block(msg_blob)
            block = block_dictionary_to_block_struct(block_dict)
            await self.return_msg(_id, block.to_bytes_packed())

        elif msg_type == BLOCK_INDEX_REQUEST and self.driver is not None:
            pass

        elif msg_type == BLOCK_TOP_NUM:
            await self.return_msg(_id, self.top.get_latest_block_number())

        elif msg_type == BLOCK_TOP_HASH:
            await self.return_msg(_id, self.top.get_latest_block_hash())

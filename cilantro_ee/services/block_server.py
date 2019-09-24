from cilantro_ee.protocol.comm.services import AsyncInbox, SocketStruct, Protocols
from cilantro_ee.messages import capnp as schemas
import os
import capnp

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


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


class BlockServer(AsyncInbox):
    def __init__(self, driver):
        self.driver = driver
        super().__init__()

    async def handle_msg(self, _id, msg):
        idx = msg[0]
        block_dict = await self.driver.get_block(idx)
        block = block_dictionary_to_block_struct(block_dict)
        await self.return_msg(_id, block.to_bytes_packed())

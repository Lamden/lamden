from cilantro.storage.mongo import MDB
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.messages.block_data.block_data import BlockData, BlockMetaData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
import dill, ujson as json, textwrap, bson
from bson.objectid import ObjectId
from typing import List
from cilantro.utils import Hasher
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.data import TransactionData

GENESIS_HASH = '0' * 64
OID = '5bef52cca4259d4ca5607661'

class StorageDriver:

    state_id = ObjectId(OID)

    @classmethod
    def store_block(cls, block: BlockData, validate: bool=False):
        if validate:
            block.validate()

        block_dict = MDB.get_dict(block)

        if MasterOps.evaluate_wr(entry = block_dict) is True:
            return True
        # block_dict = MDB.get_dict(block)
        # MDB.mn_db['blocks'].insert_one(block_dict)
        # MDB.mn_db['state'].update_one({'_id': cls.state_id}, {'$set': {
        #     '_id': cls.state_id,
        #     'lastest_block_hash': block_dict['block_hash']
        # }}, upsert=True)

    @classmethod
    def get_transactions(cls, block_hash=None, raw_tx_hash=None, status=None):
        # TODO verify
        pass
        # assert block_hash or raw_tx_hash or status, 'Must provide at least one search criteria'
        # query = {}
        # if block_hash:
        #     query['block_hash'] = block_hash
        # if raw_tx_hash:
        #     query['raw_tx_hash'] = raw_tx_hash
        # if status:
        #     query['status'] = status
        # return MDB.mn_db['transactions'].find(query)

    @classmethod
    def get_latest_block_hash(cls):
        # TODO verify
        pass
        # state = MDB.mn_db['state'].find_one({'_id': cls.state_id})
        # if state:
        #     return state['lastest_block_hash']
        # else:
        #     return GENESIS_HASH

    @classmethod
    def get_blocks(cls, block_hash):
        # TODO verify
        pass
        # block_dict = MDB.mn_db['blocks'].find_one({
        #     'block_hash': start_block_hash
        # })
        # assert block_dict.get(block_num), 'Block for block_hash "{}" is not found'.format(start_block_hash)
        # return MDB.mn_db['blocks'].find({
        #     'block_num': {'$gt': block_dict['block_num']}
        # })

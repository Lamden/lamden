import cilantro_ee
from cilantro_ee.crypto.wallet import Wallet
from pymongo import MongoClient, DESCENDING
from cilantro_ee.logger.base import get_logger
from bson.objectid import ObjectId
from collections import defaultdict
from cilantro_ee.crypto.canonical import block_from_subblocks

REPLICATION = 3
GENESIS_HASH = b'\x00' * 32
OID = '5bef52cca4259d4ca5607661'


class MasterStorage:
    BLOCK = 0
    INDEX = 1
    TX = 2

    def __init__(self, port=27027, config_path=cilantro_ee.__path__[0]):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.port = port

        self.client = MongoClient()
        self.db = self.client.get_database('blockchain')

        self.blocks = self.db['blocks']
        self.indexes = self.db['index']
        self.txs = self.db['tx']

        if self.get_block(0) is None:
            self.put({
                'blockNum': 0,
                'hash': b'\x00' * 32,
                'blockOwners': [b'\x00' * 32]
            }, MasterStorage.BLOCK)

            self.put({
                'blockNum': 0,
                'hash': b'\x00' * 32,
                'blockOwners': [b'\x00' * 32]
            }, MasterStorage.INDEX)

    def q(self, v):
        if isinstance(v, int):
            return {'blockNum': v}
        return {'hash': v}

    def get_block(self, v=None):
        if v is None:
            return None

        q = self.q(v)
        block = self.blocks.find_one(q)

        if block is not None:
            block.pop('_id')

        return block

    def put(self, data, collection=BLOCK):
        if collection == MasterStorage.BLOCK:
            _id = self.blocks.insert_one(data)
        elif collection == MasterStorage.INDEX:
            _id = self.indexes.insert_one(data)
        elif collection == MasterStorage.TX:
            _id = self.txs.insert_one(data)
        else:
            return False

        return _id is not None

    def get_last_n(self, n, collection=INDEX):
        if collection == MasterStorage.BLOCK:
            c = self.blocks
        elif collection == MasterStorage.INDEX:
            c = self.indexes
        else:
            return None

        block_query = c.find({}, {'_id': False}).sort(
            'blockNum', DESCENDING
        ).limit(n)

        blocks = [block for block in block_query]

        if len(blocks) > 1:
            first_block_num = blocks[0].get('blockNum')
            last_block_num = blocks[-1].get('blockNum')

            assert first_block_num > last_block_num, "Blocks are not descending."

        return blocks

    def get_owners(self, v):
        q = self.q(v)
        index = self.indexes.find_one(q)

        if index is None:
            return index

        owners = index.get('blockOwners')

        return owners

    def get_index(self, v):
        q = self.q(v)
        block = self.indexes.find_one(q)

        if block is not None:
            block.pop('_id')

        return block

    def get_tx(self, h):
        tx = self.txs.find_one({'hash': h})

        if tx is not None:
            tx.pop('_id')

        return tx

#    def put_tx_map(self, block: BlockData):
#        m = block.get_tx_hash_to_merkle_leaf()
#        blk_id = block.block_num
#
#        for entry in m:
#            entry['block'] = blk_id
#            self.txs.collection.insert_one(entry)

    def drop_collections(self):
        self.blocks.remove()
        self.indexes.remove()


class DistributedMasterStorage(MasterStorage):
    def __init__(self, key, distribute_writes=False, config_path=cilantro_ee.__path__[0], vkbook=None):
        super().__init__(config_path=config_path)

        self.distribute_writes = distribute_writes
        self.vkbook = vkbook

        self.wallet = Wallet(seed=key)

        self.sk = self.wallet.signing_key()
        self.vk = self.wallet.verifying_key()

        self.test_hook = False
        self.mn_id = 1
        self.rep_factor = 3
        self.active_masters = 12
        self.quorum_needed = 3

    def get_master_set(self):
        if self.test_hook is True:
            return self.active_masters
        else:
            self.active_masters = len(self.vkbook.masternodes)
            return self.active_masters

    def set_mn_id(self, vk):
        if self.test_hook is True:
            return self.mn_id

        # this should be rewritten to just pull from Phonebook because it's dynamic now

        for i in range(self.get_master_set()):
            if self.vkbook.masternodes[i] == vk:
                self.mn_id = i
                return True
            else:
                self.mn_id = -1
                return False

    def rep_pool_sz(self):
        if self.active_masters < self.rep_factor:
            return -1

        self.active_masters = self.get_master_set()
        pool_sz = round(self.active_masters / self.rep_factor)
        return pool_sz

    def build_wr_list(self, curr_node_idx=0, jump_idx=1):
        # Use slices to make this a one liner
        tot_mn = len(self.vkbook.masternodes)
        mn_list = []

        # if quorum req not met jump_idx is 0 wr on all active nodes
        if jump_idx == 0:
            return self.vkbook.masternodes

        while curr_node_idx < tot_mn:
            mn_list.append(self.vkbook.masternodes[curr_node_idx])
            curr_node_idx += jump_idx

        return mn_list

    @staticmethod
    def index_from_block(b, nodes=[]):
        assert len(nodes) > 0, 'Must have at least one block owner!'

        index = {'blockNum': b.get('blockNum'),
                 'hash': b.get('hash'),
                 'blockOwners': nodes}

        assert index['hash'] is not None and index['blockNum'] is not None, 'Block hash and number' \
                                                                                 'must be provided!'

        return index

    def evaluate_wr(self, entry=None, node_id=None):
        """
        Function is used to check if currently node is suppose to write given entry
        :param entry: given block input to be stored
        :param node_id: master id None is default current master, if specified is for catch up case
        :return:
        """

        if entry is None:
            return False

        pool_sz = self.rep_pool_sz()
        mn_idx = self.mn_id % pool_sz
        writers = entry.get('blockNum') % pool_sz

        # TODO
        # need gov here to check if given node is voted out

        if node_id is not None:
            mn_idx = node_id % pool_sz  # overwriting mn_idx
            if mn_idx == writers:
                return True
            else:
                return False

        # always write if active master bellow threshold

        if self.active_masters < self.quorum_needed:
            self.put(entry, self.BLOCK)
            mn_list = self.build_wr_list(curr_node_idx=self.mn_id, jump_idx=0)
            index = self.index_from_block(entry, nodes=mn_list)
            return self.put(index, self.INDEX)

        if mn_idx == writers:
            self.put(entry, self.BLOCK)

        # build list of mn_sign of master nodes updating index db
        mn_list = self.build_wr_list(curr_node_idx=writers, jump_idx=pool_sz)
        assert len(mn_list) > 0, "block owner list cannot be empty - dumping list -> {}".format(mn_list)

        # create index records and update entry
        index = self.index_from_block(entry, nodes=mn_list)
        return self.put(index, self.INDEX)

    def update_index(self, block, nodes):
        index = self.index_from_block(block, nodes=nodes)
        return self.put(index, MasterStorage.INDEX)

    def put(self, data, collection=MasterStorage.BLOCK):
        super().put(data=data, collection=collection)


class CilantroStorageDriver(DistributedMasterStorage):
    def __init__(self, key, distribute_writes=False, config_path=cilantro_ee.__path__[0], **kwargs):
        self.state_id = ObjectId(OID)
        self.log = get_logger("StorageDriver")

        self.block_index_delta = defaultdict(dict)
        self.send_req_blk_num = 0

        super().__init__(key, distribute_writes=distribute_writes, config_path=config_path, **kwargs)

    def get_block_dict(self, sub_blocks, kind):
        last_block = self.get_last_n(1, self.INDEX)

        if len(last_block) > 0:
            last_block = last_block[0]
            last_hash = last_block.get('hash')
            current_block_num = last_block.get('blockNum')
        else:
            last_hash = GENESIS_HASH
            current_block_num = 0

        if kind == 0:
            current_block_num += 1

        block_dict = block_from_subblocks(subblocks=sub_blocks, previous_hash=last_hash, block_num=current_block_num)
        block_dict['blockOwners'] = [m for m in self.vkbook.masternodes],

        return block_dict

    def store_new_block(self, block):
        if block.get('blockOwners') is None:
            block['blockOwners'] = self.vkbook.masternodes
        self.evaluate_wr(entry=block)

    def store_block(self, sub_blocks):
        block_dict = self.get_block_dict(sub_blocks, kind=0)

        successful_storage = self.evaluate_wr(entry=block_dict)

        assert successful_storage is None or successful_storage is True, 'Write failure.'
        block_dict['subBlocks'] = [s for s in sub_blocks]

        return block_dict

    def get_transactions(self, tx_hash):
        txs = self.get_tx(tx_hash)

        if txs is None:
            return None

        block_num = txs.get('block')
        leaf = txs.get('tx_leaf')

        block = self.get_block(block_num)
        sub_blocks = block.get('subBlocks')

        for sb in sub_blocks:
            leaves = sb.get('merkleLeaves')

            try:
                tx_idx = leaves.index(leaf)
            except ValueError:
                tx_idx = -1

            if tx_idx >= 0:
                tx_dump = sb.get('transactions')
                return tx_dump[tx_idx]

        return None
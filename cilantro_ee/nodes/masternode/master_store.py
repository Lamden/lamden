import os
import cilantro_ee
from configparser import SafeConfigParser, ConfigParser
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.logger.base import get_logger
from cilantro_ee.storage.mongo import MDB, MasterDatabase
from cilantro_ee.messages.block_data.block_data import BlockData


class MasternodeConfig:
    def __init__(self, config_path=cilantro_ee.__path__[0]):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.config = ConfigParser()
        self.config.read(self.config_path + '/mn_db_conf.ini')

        self.test_hook = self.config.get('MN_DB', 'test_hook')
        self.mn_id = int(self.config.get('MN_DB', 'mn_id'))
        self.rep_factor = int(self.config.get('MN_DB', 'replication'))
        self.active_masters = int(self.config.get('MN_DB', 'total_mn'))
        self.quorum_needed = int(self.config.get('MN_DB', 'quorum'))


class ColdStorage:
    def __init__(self, key, vkbook=PhoneBook):
        self.config = MasternodeConfig()
        self.driver = MasterDatabase(signing_key=key)
        self.vkbook = vkbook

    def get_master_set(self):
        if self.config.test_hook is True:
            return self.config.active_masters
        else:
            self.config.active_masters = len(self.vkbook.masternodes)
            return self.config.active_masters

    def set_mn_id(self, vk):
        if self.config.test_hook is True:
            return self.config.mn_id

        # this should be rewritten to just pull from Phonebook because it's dynamic now

        for i in range(self.get_master_set()):
            if self.vkbook.masternodes[i] == vk:
                self.config.mn_id = i
                return True
            else:
                self.config.mn_id = -1
                return False

    def rep_pool_sz(self):
        if self.config.active_masters < self.config.rep_factor:
            return -1

        self.config.active_masters = self.get_master_set()
        pool_sz = round(self.config.active_masters / self.config.rep_factor)
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

    def update_idx(self, inserted_blk=None, node_list=None):

        assert node_list is not None, 'Block owner node list not provided.'

        entry = {'blockNum': inserted_blk.get('blockNum'),
                 'blockHash': inserted_blk.get('blockHash'),
                 'blockOwners': node_list}

        assert entry['blockNum'] is not None and entry['blockHash'] is not None, 'Provided block does not have a ' \
                                                                                 'number or a hash.'

        self.driver.indexes.collection.insert_one(entry)

        return True

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
        mn_idx = self.config.mn_id % pool_sz
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

        if self.config.active_masters < self.config.quorum_needed:
            self.driver.insert_block(entry)
            mn_list = self.build_wr_list(curr_node_idx=self.config.mn_id, jump_idx=0)
            return self.update_idx(inserted_blk=entry, node_list=mn_list)

        if mn_idx == writers:
            self.driver.insert_block(entry)

        # build list of mn_sign of master nodes updating index db
        mn_list = self.build_wr_list(curr_node_idx=writers, jump_idx=pool_sz)
        assert len(mn_list) > 0, "block owner list cannot be empty - dumping list -> {}".format(mn_list)

        # create index records and update entry
        return self.update_idx(inserted_blk=entry, node_list=mn_list)

    def get_full_block(self, num=None, block_hash=None):
        if num is not None:
            block = self.driver.get_block_by_number(num)
        elif block_hash is not None:
            block = self.driver.get_block_by_hash(block_hash)
        else:
            return None

        block.pop('_id')
        return block

    def get_block_idx(self, n_blocks=0):
        return self.driver.get_last_n_local_blocks(n_blocks)

    def block_number_from_block_hash(self, block_hash):
        block = self.get_full_block(block_hash=block_hash)
        return block['blockNum']

    def block_hash_from_block_number(self, num):
        block = self.get_full_block(num=num)
        return block['blockHash']

GlobalColdStorage = ColdStorage()

class MasterOps:
    @classmethod
    def update_idx(cls, inserted_blk=None, node_list=None):

        entry = {'blockNum': inserted_blk.get('blockNum'), 'blockHash': inserted_blk.get('blockHash'),
                 'blockOwners': node_list}
        MDB.insert_idx_record(entry)
        return True

    '''
        Read for particular block hash, expects to return empty if there is no block stored locally
    '''

    @classmethod
    def get_blk_idx(cls, n_blks=None):
        """
        This api takes argument of n blocks, it responds with last n block locally stored
        on mongodb
        :param n_blks:
        :return:
        """
        assert n_blks > 0, "invalid api call n_blk cannot be zero".format(n_blks)
        idx_entries = MDB.query_index(n_blks=n_blks)
        return idx_entries

    @classmethod
    def get_blk_num_frm_blk_hash(cls, blk_hash=None):
        my_query = {'blockHash': blk_hash}
        outcome = MDB.query_db(type='idx', query = my_query)
        cls.log.debug("print outcome {}".format(outcome))
        blk_num = outcome.get('blockNum')
        return blk_num

    @classmethod
    def get_blk_owners(cls, blk_hash=None, blk_num = None):
        if blk_hash is not None:
            my_query = {'blockHash': blk_hash}
        elif blk_num is not None:
            my_query = {'blockNum': blk_num}
        else:
            return None

        outcome = MDB.query_db(type='idx', query = my_query)
        owners = outcome.get('blockOwners')
        cls.log.debug("print owners {}".format(outcome))
        return owners

    @classmethod
    def update_tx_map(cls, block: BlockData):
        map = block.get_tx_hash_to_merkle_leaf()
        blk_id = block.block_num

        # cls.log.important2("Tx map - {}".format(len(map)))
        for entry in map:
            entry['block'] = blk_id
            # cls.log.important2("Entry - {}".format(entry))
            MDB.insert_tx_map(txmap = entry)

    @classmethod
    def get_usr_tx_result(cls, usr_tx_hash):
        my_query = {'tx_hash': usr_tx_hash}
        outcome = MDB.query_db(type='tx', query = my_query)
        cls.log.debugv("print outcome {}".format(outcome))
        return outcome

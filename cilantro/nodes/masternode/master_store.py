import os
import cilantro
from configparser import SafeConfigParser
from cilantro.storage.vkbook import VKBook
from cilantro.logger.base import get_logger
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.storage.mongo import MDB


class MasterOps:
    """
        Class for various master operations
        - find master pool
        - validate master
        - get unique master id
    """
    log = get_logger('master_store')
    path = os.path.dirname(cilantro.__path__[0])
    cfg = SafeConfigParser()
    cfg.read('{}/mn_db_conf.ini'.format(path))

    mn_id = cfg.get('MN_DB', 'mn_id')
    rep_factor = cfg.get('MN_DB','replication')
    active_masters = cfg.get('MN_DB','total_mn')
    quorum_needed = cfg.get('MN_DB','quorum')
    test_hook = cfg.get('MN_DB','test_hook')
    init_state = False

    '''
    Config Related operations
    '''
    @classmethod
    def init_master(cls, key):
        if not cls.init_state:

            mn_id = cls.set_mn_id(key)
            if mn_id == -1:
                cls.log.info("failed to get id")

            # start/setup mongodb
            MDB.start_db()
            cls.log.info("db initiated")
            cls.init_state = True

    '''
        Checks for test hooks or finds total active masters
    '''

    @classmethod
    def get_master_set(cls):
        if cls.test_hook is False:
            cls.active_masters = len(VKBook.get_masternodes())
            return cls.active_masters
        else:
            return cls.active_masters

    '''
        Checks for test hooks or identifies current mn
    '''

    @classmethod
    def set_mn_id(cls, vk):
        if cls.test_hook is True:
            return cls.mn_id

        for i in range(cls.active_masters):
            if TESTNET_MASTERNODES[i]['vk'] == vk:
                cls.mn_id = i
                return True
            else:
                cls.mn_id = -1
                return False

    '''
        Returns sk for nth master node
        Used for updating index records for wr's
    '''
    def get_mn_sk(cls, id):
        for i in range(cls.active_masters):
            if i == id:
                return TESTNET_MASTERNODES['sk']

    '''
        Calculates pool sz for replicated writes 
    '''

    @classmethod
    def rep_pool_sz(cls):
        if cls.active_masters < cls.rep_factor:
            cls.log.error("quorum requirement not met")
            return -1

        cls.active_masters = cls.get_master_set()
        pool_sz = round(cls.active_masters/cls.rep_factor)
        return pool_sz

    @classmethod
    def evaluate_wr(cls, entry = None):
        if entry is None:
            return False

        # always write if active master bellow threshold

        if cls.active_masters < cls.quorum_needed:
            MDB.insert_record(entry)
            return cls.update_idx(entry)

        pool_sz = cls.rep_pool_sz()
        mn_idx = cls.mn_id % pool_sz
        writers = entry.get('block_num') % pool_sz

        if mn_idx == writers:
            MDB.insert_record(entry)

        # build list of mn_sign of master nodes updating index db

        mn_list = None

        # create index records and update entry
        return cls.update_idx(block_dict=entry, node_list=mn_list)

    @classmethod
    def update_idx(cls, inserted_blk=None, node_list=None):

        entry = {'block_num': inserted_blk.get('block_num'), 'block_hash': inserted_blk.get('block_hash'),
                 'master_nodes': node_list}
        MDB.insert_idx_record(entry)

    '''
        Read for particular block hash, does first read
        to index db if block is local  
    '''
    @staticmethod
    def read_bucket_entry(block_hash):
        my_query = {'block_hash', block_hash}
        outcome = MDB.query_db(query=my_query)
        return outcome



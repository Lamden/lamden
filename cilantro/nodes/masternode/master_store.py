

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
    cfg = SafeConfigParser()
    cfg.read('{}/mn_db_conf.ini'.format(path))

    rep_factor = cfg.get('MN_DB','replication')
    active_masters = cfg.get('MN_DB','total_mn')
    quorum_needed = cfg.get('MN_DB','quorum')
    test_hook = cfg.get('MN_DB','test_hook')
    init_state = False

    '''
    Config Related operations
    '''
    @classmethod
    def init_master(cls):
        if not cls.init_state:
            # start/setup mongodb
            MDB.start_db()
            cls.log.info("db initiated")
            cls.init_state = True

    @classmethod
    def get_master_set(cls):
        if cls.test_hook == False:
            cls.active_masters= len(VKBook.get_masternodes())
            return cls.active_masters
        else:
            return cls.active_masters

    # @classmethod
    # def get_rep_factor(cls):
    #
    #     rep_fact = 3  # number of replicated copies for given block
    #     return rep_fact

    @classmethod
    def set_mn_id(cls,vk):
        if cls.test_hook==True:
            mn_count = len(TESTNET_MASTERNODES)
        else:
            #TODO official lookup into vkbook block on system
            mn_count = cls.active_masters

        for i in range(mn_count):
            if TESTNET_MASTERNODES[i]['vk'] == vk:
                return i
            else:
                return -1

    @classmethod
    def rep_pool_sz(cls):
        if cls.active_masters < cls.rep_factor:
            print ("quorum requirement not met")
            return -1

        cls.active_masters = cls.get_master_set()
        pool_sz = round(cls.active_masters/cls.rep_factor)
        return pool_sz

    @staticmethod
    def mn_pool_idx(pool_sz, mn_id):
        return (mn_id % pool_sz)

    '''
        Write operations
    '''
    @staticmethod
    def check_min_mn_wr(rep_fact,mn_set, id):
        if mn_set<=rep_fact and id!=-1:
            # always wr
            return True
        return False

    @staticmethod
    def evaluate_wr(mn_idx, blk_id, pool_sz):
#        mn_idx = MasterOps.mn_pool_idx(pool_sz,mn_id)
        writer = blk_id % pool_sz
        if mn_idx == writer:
            return True
        else:
            return False

    '''
        Read operations
    '''
    @staticmethod
    def read_bucket_entry(block_hash):
        pass

    '''
        Lookup operations
    '''

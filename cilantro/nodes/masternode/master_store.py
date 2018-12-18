import os
import cilantro
from configparser import SafeConfigParser
from cilantro.storage.vkbook import VKBook
from cilantro.logger.base import get_logger
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

    mn_id = int(cfg.get('MN_DB', 'mn_id'))
    rep_factor = int(cfg.get('MN_DB', 'replication'))
    active_masters = int(cfg.get('MN_DB', 'total_mn'))
    quorum_needed = int(cfg.get('MN_DB', 'quorum'))
    test_hook = cfg.get('MN_DB', 'test_hook')
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
            # MDB.start_db(s_key = key)
            host = bool(MDB(s_key = key))
            assert host is True, "failed db init - {}".format(host)

            cls.log.info("************db initiated*************")
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

        masternode_vks = VKBook.get_masternodes()
        for i in range(cls.active_masters):
            if masternode_vks[i] == vk:
                cls.mn_id = i
                return True
            else:
                cls.mn_id = -1
                return False

    # WARNING: Masternodes do not know each other's SKs
    # '''
    #     Returns sk for nth master node
    #     Used for updating index records for wr's
    # '''
    # def get_mn_sk(cls, id):
    #     for i in range(cls.active_masters):
    #         if i == id:
    #             return TESTNET_MASTERNODES['sk']

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

    '''
        builds list master wrs base on mn id [0 - len(master)]
    '''

    @classmethod
    def build_wr_list(cls, curr_node_idx = None, jump_idx = 1):
        all_mn = VKBook.get_masternodes()
        tot_mn = len(all_mn)
        mn_list = []

        # if quorum req not met jump_idx is 0 wr on all active nodes
        if jump_idx == 0:
            mn_list = all_mn
            cls.log.debug("1 build_wr_list mn_list - {}".format(mn_list))
            return mn_list

        while curr_node_idx < tot_mn:
            mn_list.append(all_mn[curr_node_idx])
            curr_node_idx += jump_idx

        cls.log.debug("2 build_wr_list mn_list - {}".format(mn_list))
        return mn_list

    @classmethod
    def evaluate_wr(cls, entry=None, node_id=None):
        """
        Function is used to check if currently node is suppose to write given entry

        :param entry: given block input to be stored
        :param node_id: master id None is default current master, if specified is for catch up case
        :return:
        """

        if entry is None:
            return False

        # always write if active master bellow threshold

        if cls.active_masters < cls.quorum_needed:
            cls.log.debug("quorum req not met evaluate_wr blk entry {}".format(entry))
            MDB.insert_record(entry)
            mn_list = cls.build_wr_list(curr_node_idx = cls.mn_id, jump_idx = 0)
            return cls.update_idx(inserted_blk = entry, node_list = mn_list)

        pool_sz = cls.rep_pool_sz()
        mn_idx = cls.mn_id % pool_sz
        writers = entry.get('blockNum') % pool_sz

        # TODO
        # need gov here to check if given node is voted out

        if node_id:
            mn_idx = node_id % pool_sz  # overwriting mn_idx
            if mn_idx == writers:
                return True

        if mn_idx == writers:
            cls.log.debug("evaluate_wr blk entry {}".format(entry))
            MDB.insert_record(entry)

        # build list of mn_sign of master nodes updating index db
        mn_list = cls.build_wr_list(curr_node_idx = writers, jump_idx = pool_sz)
        assert len(mn_list) > 0, "block owner list cannot be empty - dumping list -> {}".format(mn_list)

        # create index records and update entry
        return cls.update_idx(inserted_blk=entry, node_list=mn_list)

    @classmethod
    def update_idx(cls, inserted_blk=None, node_list=None):

        entry = {'blockNum': inserted_blk.get('blockNum'), 'blockHash': inserted_blk.get('blockHash'),
                 'mn_blk_owner': node_list}
        MDB.insert_idx_record(entry)
        return True

    '''
        Read for particular block hash, expects to return empty if there is no block stored locally
    '''
    @classmethod
    def get_full_blk(cls, blk_num=None, blk_hash=None):
        outcome = None
        if blk_hash:
            my_query = {'blockHash': blk_hash}
            outcome = MDB.query_db(query = my_query)
            return outcome

        if blk_num:
            my_query = {'blockNum': blk_num}
            outcome = MDB.query_db(query = my_query)
            return outcome

        assert outcome is not None, "failed to get full block {}".format(outcome)

    @classmethod
    def get_blk_idx(cls, n_blks=None):
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
        owners = outcome.get('mn_blk_owner')
        cls.log.debug("print owners {}".format(outcome))
        return owners


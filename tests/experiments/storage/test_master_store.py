'''
Test to validate storage layer algorithm
Goals :
- Wr should be equally distributed
- Wr should be replicated as config

'''

from collections import defaultdict
from cilantro.protocol import wallet
from cilantro.constants.testnet import TESTNET_MASTERNODES
import json
import sys
import zmq
#import pymongo
#import pymongo.json_util

'''

class MDB(object):
    """
            start mongodb before using this
    """

    def __init__(self, database_name, table_name, bind_addr="tcp://localhost:5000"):
        """

        :param database_name: Name of db
        :param table_name: table for entries
        :param bind_addr:  address for zmq bind
        """
        self._bind_addr = bind_addr
        self._db_name = database_name
        self._tbl_name = table_name
        self._conn = pymongo.Connection()
        self._db = self._conn[self._db_name]
        self._tbl = self._db[self._tbl_name]

    def add_entries(self,data):
        """
        :param data: block data to be inserted
        :return:
        """
        try:
            self._tbl.insert(data)
        except Exception as e:
            return 'Error: %s' % e

    def _doc_to_json(self, doc):
        return json.dumps(doc, default=pymongo.json_util.default)
'''

class MasterOps:
    '''
        Class for various master operations
        - find master pool
        - validate master
        - get unique master id
    '''
    store_setup = False

    '''
    Config Related operations
    '''
    @staticmethod
    def get_master_set():   #hard coded for now
        mn_set = 12  # Quorum of masters (assuming requirement of min 3)
        return mn_set

    @staticmethod
    def get_rep_factor():   #hard coded for now
        rep_fact = 3  # number of replicated copies for given block
        return rep_fact

    @staticmethod
    def get_mn_id(vk):

        mn_count = len(TESTNET_MASTERNODES)
        for i in range(mn_count):
            if TESTNET_MASTERNODES[i]['vk'] == vk:
                return i
            else:
                return -1

    @staticmethod
    def rep_pool_sz(rep_fact, mn_set):
        if mn_set < 3:
            # should be noop currently we are hard coding
            print ("quorum requirement not met")
            return -1

        pool_sz = round(mn_set/rep_fact);
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


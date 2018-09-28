'''
Test to validate storage layer algorithm
Goals :
- Wr should be equally distributed
- Wr should be replicated as config

'''

from collections import defaultdict
from cilantro.protocol import wallet
from cilantro.constants.testnet import TESTNET_MASTERNODES

'''
Pre config values for test
'''

'''
    TEST ONLY :Following is storage class to simulate storage pool capabilities
'''

#mn_buckets = defaultdict(list)
#for i in range(mn_set):
#    mn_buckets[i].append(None)




class MasterOps:
    '''
        Class for various master operations
        - find master pool
        - validate master
        - get unique master id
    '''
    store_setup = False

    @staticmethod
    def get_master_set():   #hard coded for now
        mn_set = 12  # Quorum of masters (assuming requirement of min 3)
        return mn_set

    @staticmethod
    def get_rep_factor():   #hard coded for now
        rep_fact = 3  # number of replicated copies for given block
        return rep_fact

    @staticmethod
    def check_min_mn_wr(rep_fact,mn_set, id):
        if mn_set<=rep_fact and id!=-1:
            # always wr
            return True
        return False

    @staticmethod
    def get_mn_id(sk):

        mn_count = len(TESTNET_MASTERNODES)
        for i in range(mn_count):
            if TESTNET_MASTERNODES[i]['sk'] == sk:
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

    @staticmethod
    def evaluate_wr(mn_idx, blk_id, pool_sz):
#        mn_idx = MasterOps.mn_pool_idx(pool_sz,mn_id)
        writer = blk_id % pool_sz
        if mn_idx == writer:
            return True
        else:
            return False

    @staticmethod
    def wr_to_bucket(mn_id, blk_id):
        mn_buckets[mn_id].append(blk_id)


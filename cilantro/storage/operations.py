'''
Test to validate storage layer algorithm
Goals :
- Wr should be equally distributed
- Wr should be replicated as config

'''

from collections import defaultdict
from cilantro.protocol import wallet
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.constants.masternode import NUM_PRIMARY, REP_FACTOROR, MAX_BLOCK, TOTAL_MASTERS

'''
Pre config values for test
'''

store_setup = False

'''
    TEST ONLY :Following is storage class to simulate storage pool capabilities
'''
mn_buckets = defaultdict(list)
for i in range(TOTAL_MASTERS):
    mn_buckets[i].append(None)


'''
    Class for various master operations
'''

class StorageOperations:
    def __init__(self,signing_key, name='MN_Store', MN_id):

        # verify current node before init
        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        # TODO verify type of node to ensure capabilities
        init_store(TOTAL_MASTERS)


    def get_mn_id(self, sk):
        mn_count = len(TESTNET_MASTERNODES)
        self.signing_key = sk
        for i in range(mn_count):
            if self.signing_key == TESTNET_MASTERNODES[i]['sk']:
                return i

        return -1

    def rep_pool_sz(self):
        if TOTAL_MASTERS < REP_FACTOR:
            print ("quorum requirement not met")
            return -1

        pool_sz = round(TOTAL_MASTERS/REP_FACTOR);
        return pool_sz

    def mn_pool_idx(self,pool_sz, mn_id):
        return (mn_id % pool_sz) - 1

    def evaluate_wr(self,mn_id, blk_id, pool_sz):
        mn_idx = MasterOps.mn_pool_idx(pool_sz,mn_id)
        writer = blk_id % pool_sz
        if mn_idx == writer:
            return True
        else:
            return False

    def wr_to_bucket(self,mn_id, blk_id):
        mn_buckets[mn_id].append(blk_id)

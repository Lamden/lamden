from cilantro_ee.constants.zmq_filters import TRANSACTION_FILTERS
from cilantro_ee.constants.block import MAX_SUB_BLOCK_BUILDERS

import math

# until we have clarity on exact final form of this, keep it simple

class BlockSubBlockMapper:
    def __init__(self, mn_vk_list, txn_filter_list=TRANSACTION_FILTERS,
                 max_sb_builders=MAX_SUB_BLOCK_BUILDERS):
        assert (max_sb_builders > 0) and (len(txn_filter_list) > 0) and \
               (len(mn_vk_list) > 0), "all inputs require positive number"
        self.mn_vk_list = mn_vk_list
        self.txn_filter_list = txn_filter_list
        self.num_sub_blocks = len(txn_filter_list) * len(mn_vk_list)
        self.num_sb_builders = min(max_sb_builders, self.num_sub_blocks)
        num_blocks = math.ceil(self.num_sub_blocks / self.num_sb_builders)
        if (num_blocks == 2) and \
           (math.ceil(self.num_sub_blocks / (self.num_sb_builders - 1)) == 2):
            self.num_sb_builders -= 1
        self.num_sb_per_block = self.num_sb_builders 


    def get_num_blocks(self):
        return self.num_sb_builders * self.get_num_subscribers(0)

    def get_list_of_subscriber_list(self):
        # complete master list
        vf_list = [(v,f) for v in self.mn_vk_list for f in self.txn_filter_list]
        # now divvy up
        list_of_subscriber_list = []
        si = 0
        for sbb_idx in range(self.num_sb_builders):
            ei = si + self.get_num_subscribers(sbb_idx)
            list_of_subscriber_list.append(vf_list[si:ei])
            si = ei
        return list_of_subscriber_list

    def get_list_of_num_subscribers(self):
        list_of_num_subscribers = []
        for sbb_idx in range(self.num_sb_builders):
            n = self.get_num_subscribers(sbb_idx)
            list_of_num_subscribers.append(n)
        return list_of_num_subscribers

    def get_num_subscribers(self, sbb_index):
        assert sbb_index < self.num_sb_builders, \
          "Only {} sub-block builders are supported".format(self.num_sb_builders)
        remainder = self.num_sub_blocks % self.num_sb_builders
        num_masters = self.num_sub_blocks // self.num_sb_builders
        if sbb_index < remainder:
            num_masters += 1
        return num_masters
   

    @staticmethod
    def get_bag_index(sub_block_num: int, num_builders: int):
        return (sub_block_num // num_builders)

    @staticmethod
    def get_builder_index(sub_block_num: int, num_builders: int):
        return (sub_block_num % num_builders)

    @staticmethod
    def get_sub_block_num(bag_idx: int, builder_idx: int, num_builders: int):
        return (bag_idx * num_builders + builder_idx)


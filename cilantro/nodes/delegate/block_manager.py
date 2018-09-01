"""
    BlockManager  (main process of delegate)

    This should coordinate the resolution mechanism for inter-subblock conflicts.
    It will also stitch two subblocks into one subtree and send to master and other delegates for voting.
    And will send in its vote on other subtrees to master directly when received from other delegates

    It can also have a thin layer of row conflict info that can be used to push some transactions to next block if they are conflicting with transactions in flight
    It will rotate asking 16 sets of sub-block-builders to proceed.

    It will also get new block notifications from master and can update its thin layer caching
        ask next set of sub-block-builders to proceed
        communicate failed contracts to previous sub-block-builder (SBB) either to reject or repeat in next block
    manages a pool of 64 processes for SBB.
    also spawns a thread for overlay network

    Input:
      - responsible subtree (based on delegate ordering ??? constant until next election)

    need to decide whether this code will live in delegate.py under Delegate class or 
    Delegate class will contain this class as a data structure and manage this and other stuff
"""


MAX_SUB_BLOCKS = 64

class BlockManager:

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       # initialize
       self.current_hash = BlockStorageDriver.get_latest_block_hash()

       self.subtree_index = # delegate order / 8
       # need to coordinate its boot state with overlay network
       # once boot ready, it needs to spawn 
       for p in range(MAX_SUB_BLOCKS):
           self.witness_set[p] = self._get_witness_set(p)
           self.sbb[p] = Process(target=SubBlockBuilder, args=(self.signing_key, self.witness_set[p], self.url, self.sbb_ports[p], p))
           self.sbb[p].start()
    

   def send_make_block(self, block_num):

   async def recv_sb_merkle_sig(self):
       # need to keep in an array based on sbb_index.
       # need to resolve differences across sub-blocks in the same order
       # once the sub-tree that it is responsible for is resolved, then send its MS to master nodes and other delegates

   async def recv_sb_merkle_sigs_from_other_delegates(self):
       # perhaps can be combined with the above,
       # verify with its copy and matches, then send the vote to masters
       # only need to keep this until its own sub-tree is ready

   # need to see where we can query for # of current txns in next batch ?
   # if the total is smaller than next batch number, perhaps skip that block this time. - mainly to deal with uneven volume?
   # we could also use the strategy of master regulating its batch based on its rate of txns
   #         - so that # of txns in a batch can be anywhere betweeen L/2 to 2L  (normalizing against L txns per sec)
   #         - in this case, we only need to know that at least one batch is available at all subtrees of next block
     


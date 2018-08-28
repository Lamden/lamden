"""
    BlockManager  (main process of delegate)

    This should coordinate the resolution mechanism for inter-subblock conflicts.
    It will also stitch two subblocks into one subtree and send to master and other delegates for voting.
    And will send in its vote on other subtrees to master directly when received from other delegates

    It can also have a thin layer of row conflict info that can be used to push some transactions to next block if they
    are conflicting with transactions in flight
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
   #  master
   #    1 for every sec, batch L txns if available.   (assuming this is our normal throughput L per sec at each master)
   #    2 if not send skip batch and it has atleast one txn, then wait for 1 secs, otherwise, go to previous step
   #    3 see if it has at least L/2 txns, then batch them and send, otherwise, send skip batch and wait for 1 more sec
   #    4 see if it has at least L/4 txns, then batch them and send, otherwise, send skip batch and wait for 1 more sec
   #    5 see if it has at least L/8 txns, then batch them and send, otherwise, send skip batch and wait for 1 more sec
   #    6 send whatever txns as a batch and go back to step 1 # this is needed at some point for fairness
   # Given this scheme, delegates only have to worry about whether they have a batch or not rather than # of txns?
   # since they get either one valid batch or skip a batch every sec, they will know whether next round is skip or not.
   # the only case is when they don't get anything for a long time,
   #   in this case they can alarm to block-manager for the missing beat? which can also be input to behavior/trust tracking?
   #   block-manager can initiate the communication to other block-mgrs to see the situation with other delegates.
   #   if it is missing selectively, then either delegates can send those bags to missing delegates or throw them away if not enough reliable quorum available as another option. 
   # each delegate will keep the prev_batch_timestamp to see if they have the next one in the next sec


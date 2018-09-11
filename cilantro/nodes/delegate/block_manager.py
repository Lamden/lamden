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
    
    1. open my pub sockets
    2. create my sub sockets
    3. sub-block builder processes and socket pairs
    4. router / dealer sockets ?? 
    5. bind sub sockets to proper pubs
       main:
       subs:   masters
                 new block notification
               other delegates
       sbb:
       subs:  witnesses
"""

from cilantro.storage.db import VKBook
from cilantro.nodes import BaseNode

MAX_NUM_MASTERS = 64
MAX_BLOCKS = 4     # can be config parameter
MAX_SUB_BLOCK_BUILDERS = 16

# communication
# From master:
#   Drop witness(es) - list
#   Add witness(es) - list
#   New Block Notification
# From Delegate (BM)
#   Request Witness list
#   Request latest block hash  (can be combined with req witness list)
#   Request block data since hash
#   send sub-tree(i) with sig + data
#   Send sig for sub-tree(i)
#   send Ready ??

class BlockManager(BaseNode):

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)

       # initialize
       self.current_hash = BlockStorageDriver.get_latest_block_hash()
       self.mn_indices = {}        # mn_vk  index
       self.sb_builders = {}       # index  process      # perhaps can be consolidated with the above ?

       self.num_mnodes = self.get_max_number_of_masternodes()
       # self.num_blocks = int(self.num_mnodes / MAX_SUB_BLOCK_BUILDERS + 1)
       self.num_blocks = MAX_BLOCKS if MAX_BLOCKS < self.num_mnodes
                                    else self.num_mnodes
       self.sub_blocks_per_block = (int)(self.num_mnodes + self.num_blocks - 1)
                                        / self.num_blocks
       self.num_sb_builders = min(MAX_SUB_BLOCK_BUILDERS, self.sub_blocks_per_block)
       self.my_sb_index = self.get_my_index() % self.sub_blocks_per_block


   def run(self):
       
       # build task list first
       self.build_task_list()
       self.loop.run_until_complete(asyncio.gather(*tasks))


   def build_task_list(self):
       
       # Add router socket - where do we listen to this ?? add
       socket = ZmqAPI.add_router(ip=self.ip) 
       self.sockets.append(socket)
       self.tasks.append(self._listen_to_router(socket))  

       socket = ZmqAPI.get_socket(self.verifying_key, type=zmq.SUB)
       self.sockets.append(socket)
       # now build listening task to other delegate(s)
       for vk in VKBook.get_delegates():
           if vk != self.verifying_key:       # not to itself
               socket.connect(vk=vk)
       self.tasks.append(self._sub_to_delegate(socket))

       # first build master(s) listening tasks
       self.build_masternode_indices()  # builds mn_indices
       mn_socket = ZmqAPI.get_socket(self.verifying_key, type=zmq.SUB)
       self.dealer = ZmqAPI.get_socket(self.verifying_key, type=zmq.DEALER)
       for vk, index in self.mn_indices:
           # ip = OverlayInterface::get_node_from_vk(vk)
           # sub connection
           mn_socket.connect(vk=vk, filter=MASTERNODE_DELEGATE_FILTER, port=MN_NEW_BLOCK_PUB_PORT))

           # dealer connection
           self.dealers.connect(vk)

       self.sockets.append(mn_socket)
       self.tasks.append(self._sub_to_master(mn_socket, vk, index)

       for index in range(self.num_sb_builders):
           # create sbb processes and sockets
           self.sbb_ports[index] = port = 6000 + index       # 6000 -> SBB_PORT 
           self.sb_builders[index] = Process(target=SubBlockBuilder,
                                             args=(self.signing_key, self.url,
                                                   self.sbb_ports[index], index))  # we probably don't need to pass port if we pass index
           self.sb_builders[index].start()
           socket = ZmqAPI.get_socket(self.verifying_key, socket_type=zmq.PAIR)
           socket.connect("{}:{}".format(url, port)))
           self.sockets.append(socket)
           self.tasks.append(self._listen_to_sbb(socket, vk, index)

       # self.tasks.append(self._dealer_to_master(socket, vk, index))
           

   def get_max_number_of_masternodes(self):
       return len(VKBook.get_masternodes())

   # assuming master set is fixed - need to build a table (key: vk, value: index)
   def build_masternode_indices(self):
       for index, vk in enumerate(VKBook.get_masternodes()):
          self.mn_indices[vk] = index
       
   async def _listen_to_router(socket):
       # Events: ??
       pass
       

   async def _sub_to_delegate(self, socket, vk):
       while True:
          event = await socket->recv_event()
          
          if event == MERKLE_SUB_BLOCK:
              self.recv_merkle_tree(event)
          # elif  
       

   async def _sub_to_master(self, socket, mn_vk, mn_index):
       # Events:
       # 1. recv new block notification
       last_block_hash, last_timestamp = self.get_latest_block_hash_timestamp()
       next_block = {}

       while True:
          event = await socket->recv_event()
          
          if event == NEW_BLOCK:
             block_hash, timestamp = self.fetch_hash_timestamp(event)
             if (block_hash == last_block_hash) or (timestamp < last_timestamp):
                 continue
             num = next_block.get(block_hash, 0) + 1
             if (num == self.quorum):
                 self.update_db(event)
                 next_block = {}
             else:
                 next_block[block_hash] = num
             

   async def _listen_to_sbb(socket, vk, index):
       # Events:
       # 1. recv merkle sub-block from SB builders
       while True:
          event = await socket->recv_event()
          
          if event == MERKLE_SUB_BLOCK:
              if index == self.my_sb_index:  # responsbile for this sub-block
                  self.handle_sub_block(event)   # verify and publish to masters and other delegates
          # elif  

   def get_my_index(self):
      for index, vk in enumerate(VKBook.get_delegates()):
          if vk == self.verifying_key:
              return index


   def handle_sub_block(self, sub_block, index):
       # resolve conflicts if any with previous sub_blocks
       sub_block = self.resolve_conflicts(sub_block, index)
       # keep it in 
       self.save_and_vote(sub_block, index)


   def save_and_vote(self, sub_block, index):
       if index == self.my_sb_index:
           self.publish_sub_block(sub_block)  # to masters and other delegates
       else:
           other_sb = self.pending_sigs.get(index, None)
           if (other_sb == None):
               self.my_sub_blocks[index] = sub_block
           else:
               status = self.vote(other_sb, sub_block)
               if status:
                   self.pending_sigs[index] = None
               else:
                   self.my_sub_blocks[index] = sub_block
               

   def vote(self, other_sb, sub_block):
       bag_hash1 = other_sb.get_bag_hash()
       bag_hash2 = sub_block.get_bag_hash()
       if (bag_hash1 != bag_hash2):
           return False
       ms_hash1 = other_sb.get_root_hash()
       ms_hash2 = sub_block.get_root_hash()
       publish_vote(agree if ms_hash1 == ms_hash2 else disagree) # to all masters
       return True

   def recv_merkle_tree(self, other_sb):
       index = self.get_sub_block_index(other_sb)
       sub_block = self.my_sub_blocks.get(index, None)
       if (sub_block == None):
           self.pending_sigs[index] = other_sb
       else:
           status = self.vote(other_sb, sub_block)
           if status:
               self.my_sub_blocks[index] = None
           else:
               self.pending_sigs[index] = other_sb
       
  

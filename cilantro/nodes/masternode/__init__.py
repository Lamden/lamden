from cilantro.nodes.masternode.masternode import Masternode, MNBaseState

# Load states so they get interpretted and properly registered in Masternode's state machine
from cilantro.nodes.masternode.new_block import MNNewBlockState, MNFetchNewBlockState

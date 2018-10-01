from cilantro.constants.testnet import *

# In reality, these should be inferred from VKBook instead of hard-coded, once we start using smart contracts for
# some of these config constants
NUM_MASTERS = len(TESTNET_MASTERNODES)
NUM_WITNESSES = len(TESTNET_WITNESSES)
NUM_DELEGATES = len(TESTNET_DELEGATES)


# ////////////////////////////////////////////////
# Consensus
# ///////////////////////////////////////////////
DELEGATE_MAJORITY = math.ceil(NUM_DELEGATES * 2 / 3)
MASTERNODE_MAJORITY = math.ceil(NUM_MASTERS * 2 / 3)


# ////////////////////////////////////////////////
# Block and Sub-block
# ///////////////////////////////////////////////
_MAX_SUB_BLOCK_BUILDERS = 8
_MAX_BLOCKS = 4

TRANSACTIONS_PER_SUB_BLOCK = 128
NUM_SUB_BLOCKS = NUM_MASTERS  # same as num masternodes for now
NUM_BLOCKS = min(_MAX_BLOCKS, NUM_SUB_BLOCKS)
NUM_SB_PER_BLOCK = (NUM_SUB_BLOCKS + NUM_BLOCKS - 1) // NUM_BLOCKS
NUM_SB_BUILDERS = max(_MAX_SUB_BLOCK_BUILDERS, NUM_SB_PER_BLOCK)
NUM_SB_PER_BUILDER = (NUM_SUB_BLOCKS + NUM_SB_BUILDERS - 1) // NUM_SB_BUILDERS

assert NUM_SUB_BLOCKS >= NUM_BLOCKS, "num_blocks {} cannot be more than num_sub_blocks {}".format(NUM_BLOCKS, NUM_SUB_BLOCKS)

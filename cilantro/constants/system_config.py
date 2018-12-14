from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES, TESTNET_WITNESSES
import math


POW_COMPLEXITY = ''  # More '0's means more complicated POWs. Empty string basically disables POW


# In reality, these should be inferred from VKBook instead of hard-coded, once we start using smart contracts for
# some of these config constants
NUM_MASTERS = len(TESTNET_MASTERNODES)
NUM_WITNESSES = len(TESTNET_WITNESSES)
NUM_DELEGATES = len(TESTNET_DELEGATES)
NUM_NODES = NUM_MASTERS + NUM_WITNESSES + NUM_DELEGATES

# How long each Node will wait for the rest of the network to come online before an error is raised
MAX_BOOT_WAIT = 180 + (NUM_NODES * 3)


# ///////////////////////////////////////////////
# Consensus
# ///////////////////////////////////////////////
DELEGATE_MAJORITY = math.ceil(NUM_DELEGATES * 2 / 3)
MASTERNODE_MAJORITY = math.ceil(NUM_MASTERS * 2 / 3)


# ///////////////////////////////////////////////
# Block and Sub-block
# ///////////////////////////////////////////////
_MAX_SUB_BLOCK_BUILDERS = 4
_MAX_BLOCKS = 1  # 2

TRANSACTIONS_PER_SUB_BLOCK = 10
NUM_SUB_BLOCKS = NUM_MASTERS  # same as num masternodes for now
NUM_BLOCKS = min(_MAX_BLOCKS, NUM_SUB_BLOCKS)

# A Masternode expects to produce a block or empty block every BLOCK_TIMEOUT seconds or he will send a SkipBlockNotif
BLOCK_PRODUCTION_TIMEOUT = 30

NUM_SB_PER_BLOCK = (NUM_SUB_BLOCKS + NUM_BLOCKS - 1) // NUM_BLOCKS
NUM_SB_BUILDERS = NUM_SB_PER_BLOCK  # NUM_SB_BUILDERS = min(_MAX_SUB_BLOCK_BUILDERS, NUM_SB_PER_BLOCK)
NUM_SB_PER_BUILDER = (NUM_SUB_BLOCKS + NUM_SB_BUILDERS - 1) // NUM_SB_BUILDERS
NUM_SB_PER_BLOCK_PER_BUILDER = (NUM_SB_PER_BLOCK + NUM_SB_BUILDERS - 1) // NUM_SB_BUILDERS

assert NUM_SUB_BLOCKS >= NUM_BLOCKS, "num_blocks {} cannot be more than num_sub_blocks {}".format(NUM_BLOCKS, NUM_SUB_BLOCKS)
assert NUM_SUB_BLOCKS/NUM_SB_PER_BLOCK == NUM_BLOCKS, "NUM_SUB_BLOCKS/NUM_SB_PER_BLOCK should equal NUM_BLOCKS"
assert NUM_SB_PER_BLOCK_PER_BUILDER >= 1, "num_sub_blocks_per_block_per_builder {} cannot less than 1".format(NUM_SB_PER_BLOCK_PER_BUILDER)


# ///////////////////////////////////////////////
# Transaction Batcher
# ///////////////////////////////////////////////
# BATCH_INTERVAL = 8
# MAX_BATCH_DURATION = 8 / NUM_BLOCKS  # just to get back to 8 for now, but it has to be a function of TRANSACTIONS_PER_SUB_BLOCK
MAX_BATCH_DURATION = 1
# BATCH_INTERVAL = NUM_BLOCKS * MAX_BATCH_DURATION
BATCH_INTERVAL = 1
MAX_SKIP_TURNS = 5


# ///////////////////////////////////////////////
# Delegate
# ///////////////////////////////////////////////
MIN_NEW_BLOCK_MN_QOURUM = math.ceil(NUM_MASTERS * 2 / 3)  # Number of NewBlockNotifications needed from unique MNs


# ///////////////////////////////////////////////
# Seneca Interpreter
# ///////////////////////////////////////////////
DECIMAL_PRECISION = 18


# ///////////////////////////////////////////////
# Test Flags
# ///////////////////////////////////////////////
SHOULD_MINT_WALLET = True
NUM_WALLETS_TO_MINT = 25
MINT_AMOUNT = 10 ** 7

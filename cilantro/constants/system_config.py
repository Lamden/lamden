from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES, TESTNET_WITNESSES
import math

# In reality, these should be inferred from VKBook instead of hard-coded, once we start using smart contracts for
# some of these config constants
NUM_MASTERS = len(TESTNET_MASTERNODES)
NUM_WITNESSES = len(TESTNET_WITNESSES)
NUM_DELEGATES = len(TESTNET_DELEGATES)


# ///////////////////////////////////////////////
# Consensus
# ///////////////////////////////////////////////
DELEGATE_MAJORITY = math.ceil(NUM_DELEGATES * 2 / 3)
MASTERNODE_MAJORITY = math.ceil(NUM_MASTERS * 2 / 3)


# ///////////////////////////////////////////////
# Block and Sub-block
# ///////////////////////////////////////////////
_MAX_SUB_BLOCK_BUILDERS = 4
_MAX_BLOCKS = 1

TRANSACTIONS_PER_SUB_BLOCK = 100
NUM_SUB_BLOCKS = NUM_MASTERS  # same as num masternodes for now
NUM_BLOCKS = min(_MAX_BLOCKS, NUM_SUB_BLOCKS)
NUM_SB_PER_BLOCK = (NUM_SUB_BLOCKS + NUM_BLOCKS - 1) // NUM_BLOCKS
NUM_SB_BUILDERS = min(_MAX_SUB_BLOCK_BUILDERS, NUM_SB_PER_BLOCK)
NUM_SB_PER_BUILDER = (NUM_SUB_BLOCKS + NUM_SB_BUILDERS - 1) // NUM_SB_BUILDERS

assert NUM_SUB_BLOCKS >= NUM_BLOCKS, "num_blocks {} cannot be more than num_sub_blocks {}".format(NUM_BLOCKS, NUM_SUB_BLOCKS)
assert NUM_SUB_BLOCKS/NUM_SB_PER_BLOCK == NUM_BLOCKS, "NUM_SUB_BLOCKS/NUM_SB_PER_BLOCK should equal NUM_BLOCKS"


# ///////////////////////////////////////////////
# Transaction Batcher
# ///////////////////////////////////////////////
BATCH_INTERVAL = 5
MAX_SKIP_TURNS = 4


# ///////////////////////////////////////////////
# Delegate
# ///////////////////////////////////////////////
MIN_NEW_BLOCK_MN_QOURUM = math.ceil(NUM_MASTERS * 2 / 3)  # Number of NewBlockNotifications needed from unique MNs


# ///////////////////////////////////////////////
# Seneca Interpreter
# ///////////////////////////////////////////////
# If MOCK_INTERPRET_RANDOM_MODE=False, we use MOCK_INTERPRET_TIME
MOCK_INTERPRET_TIME = 0.05

# If MOCK_INTERPRET_RANDOM_MODE=True, we use a random value between MIN_MOCK_INTERPRET_TIME and MAX_MOCK_INTERPRET_TIME
MOCK_INTERPRET_RANDOM_MODE = True
MIN_MOCK_INTERPRET_TIME = 0.01
MAX_MOCK_INTERPRET_TIME = 0.1

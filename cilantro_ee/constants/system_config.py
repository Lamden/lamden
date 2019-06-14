from cilantro_ee.storage.vkbook import PhoneBook
import math


POW_COMPLEXITY = ''  # More '0's means more complicated POWs. Empty string basically disables POW


# In reality, these should be inferred from VKBook instead of hard-coded, once we start using smart contracts for
# some of these config constants

NUM_MASTERS = len(PhoneBook.masternodes)
NUM_WITNESSES = len(PhoneBook.witnesses)
NUM_DELEGATES = len(PhoneBook.delegates)
NUM_NODES = NUM_MASTERS + NUM_WITNESSES + NUM_DELEGATES

# How long each Node will wait for the rest of the network to come online before an error is raised
MAX_BOOT_WAIT = 600


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

TRANSACTIONS_PER_SUB_BLOCK = 20
NUM_SUB_BLOCKS = NUM_MASTERS  # same as num masternodes for now
NUM_BLOCKS = min(_MAX_BLOCKS, NUM_SUB_BLOCKS)
DUMP_TO_CACHE_EVERY_N_BLOCKS = 5

# A Masternode expects to produce a block or empty block every BLOCK_TIMEOUT seconds or he will send a SkipBlockNotif
BLOCK_PRODUCTION_TIMEOUT = 60

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
NO_ACTIVITY_SLEEP = 32         # every 32 secs, we will send out empty bags if needed to indicate heart beat
BATCH_SLEEP_INTERVAL = 1


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
# NUM_WALLETS_TO_MINT = 50

NUM_WALLETS_TO_MINT = 100
MINT_AMOUNT = 10 ** 10

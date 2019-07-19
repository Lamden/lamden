from cilantro_ee.storage.vkbook import PhoneBook
import math


POW_COMPLEXITY = ''  # More '0's means more complicated POWs. Empty string basically disables POW


# In reality, these should be inferred from VKBook instead of hard-coded, once we start using smart contracts for
# some of these config constants

NUM_MASTERS = PhoneBook.num_boot_masternodes
NUM_WITNESSES = len(PhoneBook.witnesses)
NUM_DELEGATES = PhoneBook.num_boot_delegates
NUM_NODES = NUM_MASTERS + NUM_WITNESSES + NUM_DELEGATES

# How long each Node will wait for the rest of the network to come online before an error is raised
MAX_BOOT_WAIT = 600


# ///////////////////////////////////////////////
# Consensus
# ///////////////////////////////////////////////
DELEGATE_MAJORITY = math.ceil(NUM_DELEGATES * 2 / 3)
MASTERNODE_MAJORITY = math.ceil(NUM_MASTERS * 2 / 3)

BLOCK_NOTIFICATION_QUORUM = (NUM_MASTERS + 1) // 2
FAILED_BLOCK_NOTIFICATION_QUORUM = NUM_MASTERS - BLOCK_NOTIFICATION_QUORUM + 1


# ///////////////////////////////////////////////
# Block and Sub-block
# ///////////////////////////////////////////////

DUMP_TO_CACHE_EVERY_N_BLOCKS = 5
# A Masternode expects to produce a block or empty block every BLOCK_TIMEOUT seconds or he will send a SkipBlockNotif
BLOCK_PRODUCTION_TIMEOUT = 60
TRANSACTIONS_PER_SUB_BLOCK = 20

_MAX_SUB_BLOCK_BUILDERS = 4
_MIN_BLOCKS = 1  
NUM_SUB_BLOCKS = 1  # NUM_MASTERS -- cheap trick
NUM_BLOCKS = max(_MIN_BLOCKS, (NUM_SUB_BLOCKS + _MAX_SUB_BLOCK_BUILDERS - 1) // _MAX_SUB_BLOCK_BUILDERS) # 1

# max of 1, (2 + 4 - 1) 5 // 4 = 1

NUM_SB_PER_BLOCK = (NUM_SUB_BLOCKS + NUM_BLOCKS - 1) // NUM_BLOCKS

NUM_SB_BUILDERS = min(_MAX_SUB_BLOCK_BUILDERS, NUM_SB_PER_BLOCK)
NUM_SB_PER_BUILDER = (NUM_SUB_BLOCKS + NUM_SB_BUILDERS - 1) // NUM_SB_BUILDERS
NUM_SB_PER_BLOCK_PER_BUILDER = (NUM_SB_PER_BLOCK + NUM_SB_BUILDERS - 1) // NUM_SB_BUILDERS

assert NUM_SUB_BLOCKS >= NUM_BLOCKS, "num_blocks {} cannot be more than num_sub_blocks {}".format(NUM_BLOCKS, NUM_SUB_BLOCKS)
assert NUM_SUB_BLOCKS/NUM_SB_PER_BLOCK == NUM_BLOCKS, "NUM_SUB_BLOCKS/NUM_SB_PER_BLOCK should equal NUM_BLOCKS.\n" \
                                                      "{} / {} != {}".format(NUM_SUB_BLOCKS, NUM_SB_PER_BLOCK, NUM_BLOCKS)
assert NUM_SB_PER_BLOCK_PER_BUILDER >= 1, "num_sub_blocks_per_block_per_builder {} cannot less than 1".format(NUM_SB_PER_BLOCK_PER_BUILDER)


# ///////////////////////////////////////////////
# Transaction Batcher
# ///////////////////////////////////////////////
BATCH_SLEEP_INTERVAL = 1


# ///////////////////////////////////////////////
# Delegate
# ///////////////////////////////////////////////


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

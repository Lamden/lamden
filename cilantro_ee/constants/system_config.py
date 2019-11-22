from cilantro_ee.services.storage.vkbook import PhoneBook
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

import math

POW_COMPLEXITY = ''  # More '0's means more complicated POWs. Empty string basically disables POW

# How long each Node will wait for the rest of the network to come online before an error is raised
MAX_BOOT_WAIT = 600

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

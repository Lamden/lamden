# Block Manager / Sub Block Builder Constants
# configurable parameters
BLOCK_SIZE = 50
MAX_BLOCKS = 4  # tied to replication factor we want to use. need to see checks for consistency among these parameters
MAX_SUB_BLOCK_BUILDERS = 8   # num of SBB processes at each node

TRANSACTIONS_PER_SUB_BLOCK = 128

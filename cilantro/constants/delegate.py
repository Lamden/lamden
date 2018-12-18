# Number of seconds Delegate will wait in respective states before he times out
BOOT_TIMEOUT = 30
CATCHUP_TIMEOUT = 44
CONSENSUS_TIMEOUT = 24

# Number of nodes Delegate must be able to connect to before leaving BootState
# TODO deprecate these and move to system_config.py
BOOT_REQUIRED_MASTERNODES = 1
BOOT_REQUIRED_WITNESSES = 1
RELIABILITY_FACTOR = 5

BLOCK_REQ_TIMEOUT = 5  # Timeout for BlockMetaDataRequests
TX_REQ_TIMEOUT = 8  # Timeout for TransactionRequests
NUM_WORKERS = 2

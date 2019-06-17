# Number of seconds Masternode will wait in respective states before he times out
STAGING_TIMEOUT = 30
NEW_BLOCK_TIMEOUT = 8
FETCH_BLOCK_TIMEOUT = 24

# Quorums
TOTAL_MN = 12
QUORUM = 3
MN_ID = 1

# Web Server
NUM_WORKERS = 2  # Number of Sanic worker procs
NONCE_EXPIR = 90  # Number of seconds before a nonce requested by a user expires

# Storage
REP_FACTOR = 3
MAX_BLOCK = 100
MN_BLK_DATABASE = 'mn_store'
MN_INDEX_DATABASE = 'mn_index'
TEST_HOOK = False

# Block Aggregator
BLOCK_TIMEOUT_POLL = 2.0  # how often BlockAggregator should check if the current block being produced has timed out

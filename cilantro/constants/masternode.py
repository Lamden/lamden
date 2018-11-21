# Number of seconds Masternode will wait in respective states before he times out
STAGING_TIMEOUT = 30
NEW_BLOCK_TIMEOUT = 8
FETCH_BLOCK_TIMEOUT = 24

# Quorums
TOTAL_MN = 12
QUORUM = 3
MN_ID = 1

# Web Server
WEB_SERVER_PORT = 8080
NUM_WORKERS = 2  # Number of Sanic worker procs
NONCE_EXPIR = 90  # Number of seconds before a nonce requested by a user expires

# Storage
REP_FACTOR = 3
MAX_BLOCK = 100
MN_BLK_DATABASE = 'mn_store'
MN_INDEX_DATABASE = 'mn_index'
TEST_HOOK = False


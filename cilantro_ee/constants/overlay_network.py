from os import getenv as env

ALPHA = 2
KSIZE = 4
MAX_PEERS = 64

AUTH_TIMEOUT = 20
RPC_TIMEOUT = 10
FIND_NODE_HOP_TIMEOUT = 10
FIND_NODE_TIMEOUT = FIND_NODE_HOP_TIMEOUT * 4   # we should multiply by log2(network size)

# The number of discovery retries necessary before a masternode boots alone
MIN_DISCOVERY_NODES = 1
DISCOVERY_WAIT = 5
DISCOVERY_RETRIES = 3
DISCOVERY_LONG_WAIT = 30
DISCOVERY_ITER = 10

# How long OverlayClient should wait for a rdy sig from the OverlayServer until we timeout
CLIENT_SETUP_TIMEOUT = DISCOVERY_LONG_WAIT * DISCOVERY_ITER

PEPPER = env('PEPPER', 'cilantro_pepper')
EVENT_URL = 'ipc://overlay-event-ipc-sock'
CMD_URL = 'ipc://overlay-cmd-ipc-sock'

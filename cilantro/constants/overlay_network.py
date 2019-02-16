from os import getenv as env
from cilantro.protocol.overlay.kademlia.ip import get_public_ip
from cilantro.constants.test_suites import CI_FACTOR

ALPHA = 2
KSIZE = 4
MAX_PEERS = 64

AUTH_TIMEOUT = 20 * CI_FACTOR  # Times-out after retrying auth for the interval
RPC_TIMEOUT = 10
FIND_NODE_HOP_TIMEOUT = 10
FIND_NODE_TIMEOUT = FIND_NODE_HOP_TIMEOUT * 4   # we should multiply by log2(network size)

# The number of discovery retries necessary before a masternode boots alone
MIN_DISCOVERY_NODES = 1
DISCOVERY_WAIT = 6
DISCOVERY_RETRIES = 10
DISCOVERY_LONG_WAIT = 120
if env('VMNET'):
    DISCOVERY_ITER = 100
else:
    DISCOVERY_ITER = 10



# How long OverlayClient should wait for a rdy sig from the OverlayServer until we timeout
CLIENT_SETUP_TIMEOUT = DISCOVERY_LONG_WAIT * DISCOVERY_ITER


if env('HOST_IP'):
    HOST_IP = env('HOST_IP')
else:
    HOST_IP = get_public_ip()

PEPPER = env('PEPPER', 'cilantro_pepper')
EVENT_URL = 'ipc://overlay-event-ipc-sock-{}'.format(env('HOST_NAME', ''))
CMD_URL = 'ipc://overlay-cmd-ipc-sock-{}'.format(env('HOST_NAME', ''))

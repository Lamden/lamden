from os import getenv as env
from cilantro.protocol.overlay.ip import get_public_ip

ALPHA = 3
KSIZE = 20
MAX_PEERS = 64

AUTH_TIMEOUT = 20
RPC_TIMEOUT = 10
FIND_NODE_HOP_TIMEOUT = 10
FIND_NODE_TIMEOUT = FIND_NODE_HOP_TIMEOUT * 4   # we should multiply by log2(network size)

MIN_DISCOVERY_NODES = 1
MIN_BOOTSTRAP_NODES = 1
DISCOVERY_TIMEOUT = 3
DISCOVERY_RETRIES = 100


RETRIES_BEFORE_SOLO_BOOT = 5  # The number of discovery retries necessary before a masternode boots alone

# How long OverlayClient should wait for a rdy sig from the OverlayServer until we timeout
CLIENT_SETUP_TIMEOUT = DISCOVERY_TIMEOUT * DISCOVERY_RETRIES


if env('HOST_IP'):
    HOST_IP = env('HOST_IP')
else:
    HOST_IP = get_public_ip()

PEPPER = env('PEPPER', 'cilantro_pepper')
EVENT_URL = 'ipc://overlay-event-ipc-sock-{}'.format(env('HOST_NAME', ''))
CMD_URL = 'ipc://overlay-cmd-ipc-sock-{}'.format(env('HOST_NAME', ''))

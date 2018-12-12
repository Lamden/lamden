from os import getenv as env
from cilantro.protocol.overlay.ip import get_public_ip
from cilantro.constants.test_suites import CI_FACTOR

ALPHA = 3
KSIZE = 20
MAX_PEERS = 64

AUTH_TIMEOUT = 20 * CI_FACTOR  # Times-out after retrying auth for the interval
RPC_TIMEOUT = 10
CLIENT_SETUP_TIMEOUT = 20  # How long OverlayClient should wait for a rdy sig from the OverlayServer until we timeout
DISCOVERY_TIMEOUT = 3

DISCOVERY_RETRIES = 100
MIN_BOOTSTRAP_NODES = 1

if env('HOST_IP'):
    HOST_IP = env('HOST_IP')
else:
    HOST_IP = get_public_ip()

PEPPER = env('PEPPER', 'cilantro_pepper')
EVENT_URL = 'ipc://overlay-event-ipc-sock-{}'.format(env('HOST_NAME', ''))
CMD_URL = 'ipc://overlay-cmd-ipc-sock-{}'.format(env('HOST_NAME', ''))

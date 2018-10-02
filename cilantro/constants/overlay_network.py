ALPHA = 3
KSIZE = 20
MAX_PEERS = 64

AUTH_INTERVAL = 0.5 # Retries every second
AUTH_TIMEOUT = 5  # Times-out after retrying auth for the interval
RPC_TIMEOUT = 10  # use 3 in prod
CLIENT_SETUP_TIMEOUT = 24  # How long OverlayClient should wait for a rdy sig from the OverlayServer until we timeout

DISCOVERY_TIMEOUT = 2
MIN_BOOTSTRAP_NODES = 2

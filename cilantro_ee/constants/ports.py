# Webservers
WEB_SERVER_PORT = 8080 # Used to serve HTTP traffic
SSL_WEB_SERVER_PORT = 443 # Used to serve HTTPS traffic

# ---------------------------------------------------------------
# Overlay Ports :10000-10009
# ---------------------------------------------------------------
DISCOVERY_PORT = 10000
AUTH_PORT = 10001
DHT_PORT = 10002
EVENT_PORT = 10003
BLOCK_SERVER = 10004

# ---------------------------------------------------------------
# Masternode Ports :10010-10019
# ---------------------------------------------------------------
MN_ROUTER_PORT = 10010
MN_PUB_PORT = 10011
MN_TX_PUB_PORT = 10012

# ---------------------------------------------------------------
# Delegate Ports :10020-10029
# ---------------------------------------------------------------
DELEGATE_ROUTER_PORT = 10020
DELEGATE_PUB_PORT = 10021
SBB_PORT_START = 10022   # only in use when witnesses are present in system (not in use in cilantro enterprise)

# ---------------------------------------------------------------
# StateSync Ports :10030-10039
# ---------------------------------------------------------------
SS_ROUTER_PORT = 10030
SS_PUB_PORT = 10031

OVERLAY_SERVER = 10777

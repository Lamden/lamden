import configparser, os

CIL_CONF_PATH = '/etc/cilantro_ee.conf'

HOST_IP = None
BOOTNODES = []
RESET_DB = False
CONSTITUTION_FILE = None
SSL_ENABLED = None
NONCE_ENABLED = None
VK_IP_MAP = {}
STAMPS_ENABLED = False
LOG_LEVEL = None
SEN_LOG_LEVEL = None
SK = None

SETUP = False

if not SETUP:
    # Logger is just for debugging
    from cilantro_ee.logger.base import get_logger

    log = get_logger("CilantroConf")

    if os.path.exists(CIL_CONF_PATH):
        config = configparser.ConfigParser()
        config.read(CIL_CONF_PATH)
        config = config['DEFAULT']
        CONSTITUTION_FILE = config['constitution_file']
        BOOTNODES = config['boot_ips'].split(',')
        SK = config['sk']
        RESET_DB = config.getboolean('reset_db')
        SSL_ENABLED = config.getboolean('ssl_enabled')
        NONCE_ENABLED = config.getboolean('nonce_enabled') or False
        STAMPS_ENABLED = config.getboolean('metering')
        FLUCTUATING_QUORUMS = config.getboolean('fluctuating_quorums')
        LOG_LEVEL = int(config['log_lvl'])
        SEN_LOG_LEVEL = int(config['seneca_log_lvl']) if 'seneca_log_lvl' in config else 0

    SETUP = True


import configparser, os
import requests
CIL_CONF_PATH = '/etc/cilantro_ee.conf'

# HOST_IP = None
RESET_DB = False
CONSTITUTION_FILE = None
SSL_ENABLED = None
LOG_LEVEL = None
SEN_LOG_LEVEL = None
SK = None
BOOT_MASTERNODE_IP_LIST = []
BOOT_DELEGATE_IP_LIST = []
BOOTNODES = []
HOST_VK = None
EPOCH_INTERVAL = 1
DEFAULT_DIFFICULTY = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
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
        SK = config['sk']
        RESET_DB = config.getboolean('reset_db')
        SSL_ENABLED = config.getboolean('ssl_enabled')
        LOG_LEVEL = int(config['log_lvl'])
        SEN_LOG_LEVEL = int(config['seneca_log_lvl']) if 'seneca_log_lvl' in config else 0
        BOOT_MASTERNODE_IP_LIST = config['boot_masternode_ips'].split(',')
        BOOT_DELEGATE_IP_LIST = config['boot_delegate_ips'].split(',')
        BOOTNODES = BOOT_MASTERNODE_IP_LIST + BOOT_DELEGATE_IP_LIST
        HOST_IP = requests.get('https://api.ipify.org').text

    SETUP = True

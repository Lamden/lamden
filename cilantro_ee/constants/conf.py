import configparser, os, json

CIL_CONF_PATH = '/etc/cilantro_ee.conf'

class CilantroConf:

    HOST_IP = None
    BOOTNODES = []
    RESET_DB = False
    CONSTITUTION_FILE = None
    SSL_ENABLED = None
    NONCE_ENABLED = None
    STAMPS_ENABLED = False
    LOG_LEVEL = None
    SEN_LOG_LEVEL = None
    SK = None

    SETUP = False

    @classmethod
    def setup(cls):
        if not cls.SETUP:
            # Logger is just for debugging
            from cilantro_ee.logger.base import get_logger
            log = get_logger("CilantroConf")

            # assert os.path.exists(CIL_CONF_PATH), "No config file found at path {}. Comon man get it together!".format(CIL_CONF_PATH)

            if os.path.exists(CIL_CONF_PATH):
                config = configparser.ConfigParser()
                config.read(CIL_CONF_PATH)
                config = config['DEFAULT']

                cls.CONSTITUTION_FILE = config['constitution_file']
                cls.BOOTNODES = config['boot_ips'].split(',')
                cls.RESET_DB = config.getboolean('reset_db')
                cls.SSL_ENABLED = config.getboolean('ssl_enabled')
                cls.NONCE_ENABLED = config.getboolean('nonce_enabled') or False
                cls.STAMPS_ENABLED = config.getboolean('stamps')
                cls.LOG_LEVEL = int(config['log_lvl'])
                cls.SEN_LOG_LEVEL = int(config['seneca_log_lvl']) if 'seneca_log_lvl' in config else 0
                cls.SK = config['sk']

            cls.SETUP = True

CilantroConf.setup()

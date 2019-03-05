import configparser, os

CIL_CONF_PATH = '/etc/cilantro_ee.conf'


class ConfMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)

        assert hasattr(clsobj, 'setup'), "Class obj {} expected to have method called 'setup'".format(clsobj)
        clsobj.setup()

        return clsobj


class CilantroConf(metaclass=ConfMeta):

    HOST_IP = None
    BOOTNODES = []
    RESET_DB = False
    CONSTITUTION_FILE = None
    SSL_ENABLED = None
    NONCE_ENABLED = None
    VK_IP_MAP = {
"6abda7bc485944cc3b190309e8006b446183ed5c3c419b042fa6f2375e787bb4":"13.57.26.58",
"3906d9907f6b9621f36a6a24553201cf22b4fc2e454a9adae1e4763d1045208f":"52.53.245.135",
"7980bbd1b667b120d50219a7df34ba9c1ef4c95c2596ed74481298361ef26142":"54.153.61.124",
"2584c6f816b55fd66a6a17e32cc9495ef8b93777cfe54a25b790f54702d7ac3f":"54.193.52.212"
                }

    @classmethod
    def setup(cls):
        if os.path.exists(CIL_CONF_PATH):
            config = configparser.ConfigParser()
            config.read(CIL_CONF_PATH)
            config = config['DEFAULT']

            cls.HOST_IP = config['ip']
            cls.CONSTITUTION_FILE = config['constitution_file']
            cls.BOOTNODES = config['boot_ips'].split(',')
            cls.RESET_DB = config.getboolean('reset_db')
            cls.SSL_ENABLED = config.getboolean('ssl_enabled')
            cls.NONCE_ENABLED = config.getboolean('nonce_enabled') or False

            # DEBUG -- TODO DELETE
            from cilantro_ee.logger.base import get_logger
            log = get_logger("ConfDebug")
            log.important("BOOT IP FROM CONFIG FILE: {}".format(config['boot_ips']))
            log.important("BOOT IP CLASS VAR: {}".format(cls.BOOTNODES))
            log.important("HOST IP CLASS VAR: {}".format(cls.HOST_IP))
            log.important("SSL ENABLED CLASS VAR: {}".format(cls.SSL_ENABLED))
            log.important("NONCE ENABLED CLASS VAR: {}".format(cls.NONCE_ENABLED))
            # END DEBUG

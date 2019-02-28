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
    BOOTNODES = None
    RESET_DB = False
    CONSTITUTION_FILE = None
    SSL_ENABLED = None

    @classmethod
    def setup(cls):
        if os.path.exists(CIL_CONF_PATH):
            config = configparser.ConfigParser()
            config.read(CIL_CONF_PATH)
            config = config['DEFAULT']

            cls.SSL_ENABLED = config.getboolean('ssl_enabled')
            cls.HOST_IP = config['ip']
            cls.CONSTITUTION_FILE = config['constitution_file']
            cls.BOOT_IPS = config['boot_ips'].split(',')
            cls.RESET_DB = config.getboolean('reset_db')

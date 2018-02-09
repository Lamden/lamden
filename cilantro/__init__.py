import configparser
from pkg_resources import resource_filename
conf = resource_filename(__name__, 'cilantro.conf')
config = configparser.ConfigParser()

settings = config.read(conf)
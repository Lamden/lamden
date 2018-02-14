import configparser
from pkg_resources import resource_filename
conf = resource_filename(__name__, 'cilantro.conf')
config = configparser.ConfigParser()
config.read(conf)

# TODO -- investigate why config['default'] key does not exist (line below is giving runtime error)
# print(config['default'].get('masternode_ip'), config['default'].get('delegate_ip'), config['default'].get('witness_ip'))

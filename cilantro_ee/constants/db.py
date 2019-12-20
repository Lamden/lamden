import os
import configparser
import cilantro_ee

settings = configparser.ConfigParser()
settings._interpolation = configparser.ExtendedInterpolation()
this_dir = os.path.dirname(__file__)
db_conf_path = os.path.join(cilantro_ee.__path__[0], '/config/mn_db_conf.ini')

settings.read(db_conf_path)

# TODO deprecate ad-hoc stuff for VMNet. Use unified approach of loading settings from config file
# # If this is being run on VMNet, HOST_IP will be set. In this case we want to use preset DB_SETTINGS
# if os.getenv('HOST_IP'):
#     DB_SETTINGS = {'username': 'root',
#                    'password': '',
#                    'db': 'cilantro_ee_dev',
#                    'host': '127.0.0.1'
#                    }
# # Otherwise, this code is being run locally for unit test or on CI. In this case, we use our DB config file
# else:
DB_SETTINGS = {'username': settings.get('MN_DB', 'username'),
               'password': settings.get('MN_DB', 'password'),
               'db': settings.get('MN_DB', 'database'),
               'host': settings.get('MN_DB', 'hostname')
               }

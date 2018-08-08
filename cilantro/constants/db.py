import os
import configparser


settings = configparser.ConfigParser()
settings._interpolation = configparser.ExtendedInterpolation()
this_dir = os.path.dirname(__file__)
db_conf_path = os.path.join(this_dir, '../../db_conf.ini')

settings.read(db_conf_path)

# TODO deprecate ad-hoc stuff for VMNet. Use unified approach of loading settings from config file
# If this is being run on VMNet, HOST_IP will be set. In this case we want to use preset DB_SETTINGS
if os.getenv('HOST_IP'):
    DB_SETTINGS = {'username': 'root',
                   'password': '',
                   'db': '',
                   'host': '127.0.0.1'
                   }
# Otherwise, this code is being run locally for unit test or on CI. In this case, we use our DB config file
else:
    DB_SETTINGS = {'username': settings.get('DB', 'username'),
                   'password': settings.get('DB', 'password'),
                   'db': settings.get('DB', 'database'),
                   'host': settings.get('DB', 'hostname')
                   }

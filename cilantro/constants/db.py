import os
import configparser


settings = configparser.ConfigParser()
settings._interpolation = configparser.ExtendedInterpolation()
this_dir = os.path.dirname(__file__)
db_conf_path = os.path.join(this_dir, '../../db_conf.ini')

settings.read(db_conf_path)

DB_SETTINGS = { 'username': settings.get('DB', 'username'),
  'password': settings.get('DB', 'password'),
  'db': settings.get('DB', 'database'),
  'host': settings.get('DB', 'hostname')
}


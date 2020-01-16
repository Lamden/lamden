from pymongo import MongoClient
import configparser, os, time, sys
import cilantro_ee


def create_user(delay):
    print('Creating user for Mongo with start delay of {}...'.format(delay))
    time.sleep(delay)

    settings = configparser.ConfigParser()
    settings._interpolation = configparser.ExtendedInterpolation()
    db_conf_path = cilantro_ee.__path__[0] + '/config/mn_db_conf.ini'
    settings.read(db_conf_path)
    client = MongoClient()
    db = client.admin

    db.add_user(
        settings.get('MN_DB', 'username'),
        settings.get('MN_DB', 'password'),
        roles=[{'role': 'userAdminAnyDatabase', 'db': 'admin'}]
    )

    print("Done creating Mongo user")


if __name__ == '__main__':
    _delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    create_user(_delay)

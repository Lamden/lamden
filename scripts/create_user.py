from pymongo import MongoClient
import configparser, time
import os
import time


def create_user():
    print('Creating user for Mongo...')
    settings = configparser.ConfigParser()
    settings._interpolation = configparser.ExtendedInterpolation()
    db_conf_path = './mn_db_conf.ini'
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
    create_user()

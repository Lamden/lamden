import subprocess
from rocks.client import RocksDBClient, RocksServerOfflineError
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError


def start_rocks():
    try:
        c = RocksDBClient()
        c.ping()
    except RocksServerOfflineError:
        subprocess.Popen(['rocks', 'serve'],
                         stdout=open('/dev/null', 'w'),
                         stderr=open('/dev/null', 'w'))


def start_mongo():
    try:
        c = MongoClient(serverSelectionTimeoutMS=200)
        c.server_info()
    except ServerSelectionTimeoutError:
        subprocess.Popen(['mongod', '--dbpath ~/blocks', '--logpath /dev/null', '--bind_ip_all'],
                         stdout=open('/dev/null', 'w'),
                         stderr=open('/dev/null', 'w'))

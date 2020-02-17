import subprocess
from rocks.client import RocksDBClient, RocksServerOfflineError


def start_rocks():
    c = RocksDBClient()
    try:
        c.ping()
    except RocksServerOfflineError:
        subprocess.Popen(['rocks', 'serve'], stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))


def start_mongo():
    pass

from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.constants import conf

import time
from pymongo import MongoClient

MASTERNODE = 0
DELEGATE = 1
WITNESS = 2


def wait_for_redis():
    time.sleep(2)


def wait_for_mongo():
    while True:
        try:
            info = MongoClient().server_info()
            print("Mongo ready! Server info:\n{}".format(info))
            break
        except:
            print("Waiting for Mongo to be ready...")
            time.sleep(1)


def start_node(signing_key, node_type):
    wait_for_redis()

    if node_type == MASTERNODE:
        wait_for_mongo()

        Masternode(ip=conf.HOST_IP, name='Masternode', signing_key=signing_key)

    elif node_type == DELEGATE:
        Delegate(ip=conf.HOST_IP, name='Delegate', signing_key=signing_key)

import requests
import pathlib
import json
import os
import asyncio
import subprocess
from subprocess import call

import zmq.asyncio

from rocks.client import RocksDBClient, RocksServerOfflineError
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate


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


def print_ascii_art():
    print('''
                ##
              ######
            ####  ####
          ####      ####
        ####          ####
      ####              ####
        ####          ####
          ####      ####
            ####  ####
              ######
                ##

 ~ V I V A ~ L A ~ L A M D E N ! ~
''')


def clear():
    call('clear' if os.name == 'posix' else 'cls')


def is_valid_ip(s):
    components = s.split('.')
    if len(components) != 4:
        return False

    for component in components:
        if int(component) > 255:
            return False

    return True


def resolve_constitution(fp):
    path = pathlib.PosixPath(fp).expanduser()

    path.touch()

    f = open(str(path), 'r')
    j = json.load(f)
    f.close()

    assert 'masternodes' in j.keys(), 'No masternodes section.'
    assert 'masternode_min_quorum' in j.keys(), 'No masternode_min_quorum section.'
    assert 'delegates' in j.keys(), 'No delegates section.'
    assert 'delegate_min_quorum' in j.keys(), 'No delegate_min_quorum section.'

    return j


def start_node(args):
    assert args.node_type == 'masternode' or args.node_type == 'delegate', \
        'Provide node type as "masternode" or "delegate"'

    sk = bytes.fromhex(args.key)

    wallet = Wallet(seed=sk)

    bootnodes = []

    for node in args.boot_nodes:
        assert is_valid_ip(node), 'Invalid IP string provided to boot node argument.'
        bootnodes.append(f'tcp://{node}')

    assert len(bootnodes) > 0, 'Must provide at least one bootnode.'

    const = resolve_constitution(args.constitution)

    ip_str = requests.get('http://api.ipify.org').text
    socket_base = f'tcp://{ip_str}'

    # Start rocks
    start_rocks()
    print('starting rocks')

    if args.node_type == 'masternode':
        # Start mongo
        start_mongo()

        n = Masternode(
            wallet=wallet,
            ctx=zmq.asyncio.Context(),
            socket_base=socket_base,
            bootnodes=bootnodes,
            constitution=const,
            webserver_port=args.webserver_port,
        )
    elif args.node_type == 'delegate':
        n = Delegate(
            wallet=wallet,
            ctx=zmq.asyncio.Context(),
            socket_base=socket_base,
            bootnodes=bootnodes,
            constitution=const,
        )

    loop = asyncio.get_event_loop()
    asyncio.async(n.start())
    loop.run_forever()

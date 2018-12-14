import os, sys, hashlib
from os.path import dirname, abspath, join
from cilantro.constants.system_config import DECIMAL_PRECISION
from dotenv import load_dotenv

import cilantro
local_path = abspath(dirname(cilantro.__path__[0]))
os.environ['LOCAL_PATH'] = local_path
load_dotenv(join(local_path, 'docker', os.getenv('HOST_NAME', ''), 'redis.env'))

# Add /messages/capnp to Python path. We need these loaded for capnp magic imports
sys.path.append(os.path.dirname(__file__) + '/messages/capnp')

# Set the decimal precision for floating point arithmetic
from decimal import getcontext
getcontext().prec = DECIMAL_PRECISION


# Dark hack to block until mongo/redis is ready, courtesy of the one and only mr falcon
# if not os.getenv('__SERVERS_READY__') and os.getenv('VMNET_DOCKER'):
#     import redis, time
#     from pymongo import MongoClient
#     r = redis.StrictRedis()
#     redis_ready = False
#     mongo_ready = False
#     while not redis_ready or not mongo_ready:
#         try:
#             r.client_list()
#             redis_ready = True
#         except:
#             print("Waiting for Redis to be ready...")
#         # try:
#         #     MongoClient()
#         #     mongo_ready = True
#         # except:
#         #     print("Waiting for Mongo to be ready...")
#         time.sleep(1)
#
#     os.environ['__SERVERS_READY__'] = 'True'

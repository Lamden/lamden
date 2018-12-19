from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('1-0-0.json')

from cilantro.logger import get_logger, overwrite_logger_level
from cilantro.nodes.factory import NodeFactory
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.storage.vkbook import VKBook
import os
import logging
import time

# overwrite_logger_level(logging.WARNING)
# overwrite_logger_level(21)
# overwrite_logger_level(11)

os.environ["NONCE_DISABLED"] = "1"
os.environ["MN_MOCK"] = "1"


print("VKBook mns {}".format(VKBook.get_masternodes()))
print("TESTNET MASTERNODES {}".format(TESTNET_MASTERNODES))

ip = '127.0.0.1'
sk = TESTNET_MASTERNODES[0]['sk']
NodeFactory.run_masternode(ip=ip, signing_key=sk, reset_db=True)
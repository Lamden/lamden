from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('1-0-0.json')

from cilantro_ee.utils.factory import NodeFactory
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
from cilantro_ee.storage.vkbook import VKBook
import os

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
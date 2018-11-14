from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('1-0-0.json')

from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.nodes.factory import NodeFactory
from cilantro.constants.overlay_network import HOST_IP


mn_sk = TESTNET_MASTERNODES[0]['sk']
NodeFactory.run_masternode(signing_key=mn_sk, ip=HOST_IP)

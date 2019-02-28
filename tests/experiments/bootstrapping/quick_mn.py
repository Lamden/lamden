from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
from cilantro_ee.nodes.factory import NodeFactory
from cilantro_ee.constants.overlay_network import HOST_IP


mn_sk = TESTNET_MASTERNODES[0]['sk']
NodeFactory.run_masternode(signing_key=mn_sk, ip=HOST_IP)

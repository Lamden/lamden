import os
from cilantro.nodes import Delegate
from cilantro.testnet_config.tx_builder import seed_wallets


slot = os.getenv('SLOT_NUM')
seed_wallets(i=slot)
d = Delegate(slot=int(slot))


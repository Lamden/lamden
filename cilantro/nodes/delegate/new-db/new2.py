s = {
    'table': None,
    'key': None,
    'values': {
        None: None
    }
}

from cilantro.models.transaction import StandardTransactionBuilder
from cilantro.protocol.wallets import ED25519Wallet as Wallet
w = Wallet.new()
ss = StandardTransactionBuilder.random_tx()

print(ss._data.payload.to_dict())

class StandardTransactionStateUpdate:
    def __init__(self, std_tx):
        pass
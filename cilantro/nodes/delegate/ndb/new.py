from cilantro.models.transaction import StandardTransactionBuilder
from cilantro.protocol.wallets import ED25519Wallet as Wallet
from cilantro.nodes.delegate.ndb.backend import LevelDBBackend


def state_query_for_tx():
    pass


class StateQuery:
    def __init__(self, table_name, backend):
        self.table_name = table_name
        self.backend = backend

    def process_tx(self, tx: dict):
        raise NotImplementedError

    def __str__(self):
        return self.table_name, self.keys


s = {
    'table': None,
    'key': None,
    'values': {
        None: None
    }
}

w = Wallet.new()
ss = StandardTransactionBuilder.random_tx()

b = LevelDBBackend('/tmp/cilantro')
b.set(b'balances', ss._data.payload.sender, ss._data.payload.amount.to_bytes(16, byteorder='big'))
print(ss._data.payload.to_dict())


class Encoder:
    @staticmethod
    def encode(o):
        if o.__class__ == str:
            return o.encode()
        elif o.__class__ == int:
            return o.to_bytes(16, byteorder='big')
        return o

    @staticmethod
    def int(b: bytes) -> int:
        try:
            s = b.decode()
            i = int(s)
        except:
            if b == None:
                i = 0
        return i


class StandardQuery(StateQuery):
    def __init__(self, table_name='balances', backend=LevelDBBackend('/tmp/cilantro')):
        super().__init__(table_name=table_name, backend=backend)

    def process_tx(self, tx):
        sender_balance = self.backend.get(self.table_name.encode(), tx.sender.encode())
        if sender_balance is not None and sender_balance >= tx.amount:
            receiver_balance = self.backend.get(self.table_name.encode(), tx.reciever.encode())
            print(receiver_balance)
        else:
            return None

sq = StandardQuery(table_name='balances', backend=b)
sq.process_tx(ss)
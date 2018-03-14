from cilantro.models.transaction import StandardTransactionBuilder
from cilantro.nodes.delegate.db.backend import LevelDBBackend, STATE, BALANCES, SEPARATOR
from cilantro.utils import Encoder as E
from cilantro.models.utils import int_to_decimal

def state_query_for_tx():
    pass


class StateQuery:
    def __init__(self, table_name, backend):
        self.table_name = table_name
        self.backend = backend
        self.state_table = SEPARATOR.join([STATE, self.table_name])
        self.txq_table = SEPARATOR.join([b'txq', self.table_name])

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

ss = StandardTransactionBuilder.random_tx()

b = LevelDBBackend('/tmp/cilantro')
b.set(E.encode('balances'),
      E.encode(ss.sender),
      E.encode(ss._data.payload.amount))

print(ss._data.payload.to_dict())


class StandardQuery(StateQuery):
    """
    StandardQuery
    Automates the state and txq modifications for standard transactions
    """
    def __init__(self, table_name=BALANCES, backend=LevelDBBackend('/tmp/cilantro')):
        super().__init__(table_name=table_name, backend=backend)

    def get_balance(self, address):
        if self.backend.exists(self.state_table, address.encode()):
            return int_to_decimal(E.int(self.backend.get(self.state_table, address.encode())))
        else:
            return int_to_decimal(E.int(self.backend.get(self.table_name, address.encode())))

    def process_tx(self, tx):
        sender_balance = self.get_balance(tx.sender)

        if sender_balance >= tx.amount:
            print('yes')
            receiver_balance = self.get_balance(tx.receiver)
            print(receiver_balance)



        else:
            return None


sq = StandardQuery(backend=b)
sq.process_tx(ss)
import plyvel
from cilantro.models.utils import int_to_decimal
from cilantro import Constants
from cilantro.utils import Encoder as E

SEPARATOR = b'/'
SCRATCH = b'scratch'
STATE = b'state'
BALANCES = b'balances'
TXQ = b'txq'
PATH = '/tmp/cilantro'


# def sync_state_with_scratch(backend):
#     scratch = backend.flush(SCRATCH)
#     for tx in scratch:
#         k, v = tx
#         k = k.lstrip(SCRATCH)
#         k = STATE + k
#         backend.set


class Backend:
    def get(self, table, key):
        raise NotImplementedError

    def set(self, table, key, value):
        raise NotImplementedError

    def exists(self, table, key):
        raise NotImplementedError

    def flush(self, table):
        raise NotImplementedError


class LevelDBBackend(Backend):
    def __init__(self, path=PATH):
        self.path = path

    def get(self, table: bytes, key: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        r = db.get(SEPARATOR.join([table, key]))
        db.close()
        return r

    def set(self, table: bytes, key: bytes, value: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        r = db.put(SEPARATOR.join([table, key]), value)
        db.close()
        return r

    def exists(self, table: bytes, key: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        if db.get(SEPARATOR.join([table, key])) is not None:
            db.close()
            return True
        db.close()
        return False

    def delete(self, table: bytes, key: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        db.delete(SEPARATOR.join([table, key]))
        db.close()

    def flush(self, table: bytes, return_results=True):
        results = []
        db = plyvel.DB(self.path, create_if_missing=True)
        for k, v in db.iterator(start=table):
            if return_results:
                results.append((k, v))
            db.delete(k)
        db.close()
        return results


class TransactionQueue:
    def __init__(self, backend):
        self.backend = backend
        self.size = 0
        self.table_name = TXQ

    def push(self, tx):
        self.size += 1
        prefix = self.size.to_bytes(16, byteorder='big')
        self.backend.set(self.table_name, prefix, tx)

    def pop(self):
        prefix = self.size.to_bytes(16, byteorder='big')
        tx = self.backend.get(self.table_name, prefix)
        self.backend.delete(self.table_name, prefix)
        self.size -= 1
        return tx

    def flush(self):
        return self.backend.flush(self.table_name)


class StateQuery:
    def __init__(self, table_name, backend):
        self.table_name = table_name
        self.backend = backend
        self.scratch_table = SEPARATOR.join([SCRATCH, self.table_name])

        self.txq = TransactionQueue(backend=self.backend)
        self.txq_table = SEPARATOR.join([TXQ, self.table_name])

    def process_tx(self, tx: dict):
        raise NotImplementedError

    def __str__(self):
        return self.table_name.decode()


class StandardQuery(StateQuery):
    """
    StandardQuery
    Automates the state and txq modifications for standard transactions
    """
    def __init__(self, table_name=BALANCES, backend=LevelDBBackend()):
        super().__init__(table_name=table_name, backend=backend)

    def balance_to_decimal(self, table, address):
        balance = self.backend.get(table, address.encode())
        balance = E.int(balance)
        balance = int_to_decimal(balance)
        return balance

    @staticmethod
    def encode_balance(balance):
        balance *= pow(10, Constants.Protocol.DecimalPrecision)
        balance = int(balance)
        balance = E.encode(balance)
        return balance

    def get_balance(self, address):
        if self.backend.exists(self.scratch_table, address.encode()):
            return self.balance_to_decimal(self.scratch_table, address)
        else:
            return self.balance_to_decimal(self.table_name, address)

    def process_tx(self, tx):
        sender_balance = self.get_balance(tx.sender)

        if sender_balance >= tx.amount:
            print(sender_balance)

            receiver_balance = self.get_balance(tx.receiver)

            new_sender_balance = sender_balance - tx.amount
            new_sender_balance = self.encode_balance(new_sender_balance)

            new_receiver_balance = receiver_balance + tx.amount
            new_receiver_balance = self.encode_balance(new_receiver_balance)

            self.backend.set(self.scratch_table, tx.sender.encode(), new_sender_balance)
            self.backend.set(self.scratch_table, tx.receiver.encode(), new_receiver_balance)

            self.txq.push(tx)

            return tx, (self.scratch_table, tx.sender.encode(), new_sender_balance), \
                   (self.scratch_table, tx.receiver.encode(), new_receiver_balance)
        else:
            return None, None, None
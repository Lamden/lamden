import plyvel

SEPARATOR = b'/'
STATE = b'state'
BALANCES = b'balances'


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
    def __init__(self, path):
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
                results.append(v)
            db.delete(k)
        db.close()
        return results


class TransactionQueue:
    def __init__(self, backend):
        self.backend = backend
        self.size = 0
        self.table_name = b'txq'

    def push(self, tx):
        self.size += 1
        prefix = self.size.to_bytes(16, byteorder='big')
        self.backend.set(self.table_name + prefix, tx)

    def pop(self):
        prefix = self.size.to_bytes(16, byteorder='big')
        tx = self.backend.get(self.table_name + prefix)
        self.backend.delete(self.table_name + prefix)
        self.size -= 1
        return tx

    def flush(self):
        return self.backend.flush(self.table_name)


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

    @staticmethod
    def encode_balance(balance):
        balance *= pow(10, Constants.Protocol.DecimalPrecision)
        balance = int(balance)
        balance = E.encode(balance)
        return balance

    def process_tx(self, tx):
        sender_balance = self.get_balance(tx.sender)

        if sender_balance >= tx.amount:
            print(sender_balance)

            receiver_balance = self.get_balance(tx.receiver)

            new_sender_balance = sender_balance - tx.amount
            new_sender_balance = self.encode_balance(new_sender_balance)

            new_receiver_balance = receiver_balance + tx.amount
            new_receiver_balance = self.encode_balance(new_receiver_balance)

            self.backend.set(self.state_table, tx.sender.encode(), new_sender_balance)
            self.backend.set(self.state_table, tx.receiver.encode(), new_receiver_balance)
        else:
            return None
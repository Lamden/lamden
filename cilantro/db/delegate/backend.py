import plyvel

SEPARATOR = b'/'
SCRATCH = b'scratch'
STATE = b'state'
BALANCES = b'balances'
TXQ = b'txq'
PATH = '/tmp/cilantro'
VOTES = b'votes'
SWAPS = b'swaps'


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
        if value is None:
            value = b''
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
        for k, v in db.iterator(prefix=table):
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

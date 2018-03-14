import plyvel
from cilantro.models import StandardTransaction, Message, MerkleTree, Poke
from cilantro.models.message.message import MODEL_TYPES # TODO -- find a better home for these constants

SEPARATOR = b'/'


class Backend:
    def __init__(self, *args):
        raise NotImplementedError

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
        super().__init__()
        self.db = plyvel.DB(path)

    def get(self, table: bytes, key: bytes):
        return self.db.get(SEPARATOR.join([table, key]))

    def set(self, table: bytes, key: bytes, value: bytes):
        return self.db.put(SEPARATOR.join([table, key]), value)

    def exists(self, table: bytes, key: bytes):
        if self.db.get(SEPARATOR.join([table, key])):
            return True
        return False

    def flush(self, table: bytes):
        for k, v in self.db.iterator(start=table):
            self.db.delete(k)


def state_query_for_tx():
    pass


class StateQuery:
    def __init__(self, table_name, keys, backend):
        self.table_name = table_name
        self.keys = {k: None for (k, v) in keys}
        self.backend = backend

    def __assert(self, query: dict):
        assert query.__class__ == dict, "Query must be of type dictionary"
        assert sorted(query.keys()) == sorted(self.keys.keys()), "Query must contain all the valid keys"

    def valid_query(self, query: dict):
        raise NotImplementedError

    def __get(self, query: dict):
        self.__assert(query)
        self.backend.get(self.table_name, list(query.keys()))

    def __set(self, query: dict, value: bytes):
        self.__assert(query)
        self.backend.set(self.table_name, list(query.keys()), value)

    def __exists(self, query: dict):
        self.__assert(query)
        self.backend.exists(self.table_name, list(query.keys()))

    def __flush(self):
        self.backend.flush(self.table_name)

    def __str__(self):
        return self.table_name, self.keys


class StandardQuery(StateQuery):
    def __init__(self, *args):
        super().__init__(*args)

    def valid_query(self, query: dict):
        super().valid_query(query)


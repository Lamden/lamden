from unittest import TestCase
from cilantro.db.delegate.backend import *
import secrets


class TestLevelDBBackend(TestCase):
    def test_constants_work(self):
        self.assertEqual(SEPARATOR, b'/')
        self.assertEqual(SCRATCH, b'scratch')
        self.assertEqual(STATE, b'state')
        self.assertEqual(BALANCES, b'balances')
        self.assertEqual(TXQ, b'txq')
        self.assertEqual(PATH, '/tmp/cilantro')

    def test_backend_implemented_error(self):
        b = Backend()

        def get():
            b.get(b'', b'')

        def set():
            b.set(b'', b'', b'')

        def exists():
            b.exists(b'', b'')

        def flush():
            b.flush(b'')

        self.assertRaises(NotImplementedError, get)
        self.assertRaises(NotImplementedError, set)
        self.assertRaises(NotImplementedError, exists)
        self.assertRaises(NotImplementedError, flush)

    def test_leveldb_get_set(self):
        l = LevelDBBackend()

        t = secrets.token_bytes(16)
        k = secrets.token_bytes(16)
        v = secrets.token_bytes(16)

        l.set(t, k, v)

        vv = l.get(t, k)

        self.assertEqual(v, vv)

    def test_leveldb_exists(self):
        l = LevelDBBackend()

        t = secrets.token_bytes(16)
        k = secrets.token_bytes(16)
        v = secrets.token_bytes(16)

        l.set(t, k, v)

        self.assertTrue(l.exists(t, k))

    def test_leveldb_delete(self):
        l = LevelDBBackend()

        t = secrets.token_bytes(16)
        k = secrets.token_bytes(16)
        v = secrets.token_bytes(16)

        l.set(t, k, v)

        vv = l.get(t, k)

        self.assertEqual(v, vv)

        l.delete(t, k)

        self.assertFalse(l.exists(t, k))

    def test_leveldb_flush(self):
        l = LevelDBBackend()

        t = secrets.token_bytes(16)

        ks = [secrets.token_bytes(16) for _ in range(10)]
        vs = [secrets.token_bytes(16) for _ in range(10)]

        for i in range(10):
            l.set(t, ks[i], vs[i])

        vvs = [i[1] for i in l.flush(t)]

        self.assertCountEqual(vs, vvs)

    def test_transaction_queue_push_pop(self):
        l = LevelDBBackend()
        tq = TransactionQueue(l)

        tx_1 = secrets.token_bytes(16)
        tx_2 = secrets.token_bytes(16)

        tq.push(tx_1)
        tq.push(tx_2)

        tx_2_a = tq.pop()
        tx_1_a = tq.pop()

        self.assertEqual(tx_1, tx_1_a)
        self.assertEqual(tx_2, tx_2_a)

    def test_transaction_queue_flush(self):
        l = LevelDBBackend()
        tq = TransactionQueue(l)

        tx_1 = secrets.token_bytes(16)
        tx_2 = secrets.token_bytes(16)

        tx_3 = secrets.token_bytes(16)
        tx_4 = secrets.token_bytes(16)

        tq.push(tx_1)
        tq.push(tx_2)

        l.set(b'some_table', b'some_key_1', tx_3)
        l.set(b'some_table', b'some_key_1', tx_4)

        txs = tq.flush()
        txs = [tx[1] for tx in txs]

        print(txs)

        self.assertCountEqual([tx_1, tx_2], txs)
        self.assertNotIn(tx_3, txs)
        self.assertNotIn(tx_4, txs)

    def test_state_query_string(self):
        t = b'some_table'
        l = LevelDBBackend()
        sq = StateQuery(t, l)

        self.assertEqual(str(sq), t.decode())

    def test_state_query_implemented_error(self):
        t = b'some_table'
        l = LevelDBBackend()
        sq = StateQuery(t, l)

        def process_tx():
            sq.process_tx({1: 2})

        self.assertRaises(NotImplementedError, process_tx)
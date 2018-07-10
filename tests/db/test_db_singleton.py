from unittest import TestCase
from cilantro.db import DB, DBSingletonMeta
import os
import multiprocessing


class TestDBSingleton(TestCase):

    def setUp(self):
        # Clear all DB instances between tests
        DBSingletonMeta._instances.clear()

    @staticmethod
    def _run_db_proc(shared_mem):
        with DB() as db:
            pid = os.getpid()
            shared_mem[pid] = id(db.lock)

    def test_separate_processes_separate_locks(self):
        """
        Tests that accessing DB from different processes creates separate instances with separate locks
        """
        num_procs = 4

        manager = multiprocessing.Manager()
        shared_mem = manager.dict()

        procs = [multiprocessing.Process(target=TestDBSingleton._run_db_proc, args=(shared_mem,)) for _ in range(num_procs)]
        for p in procs:
            p.start()
            p.join()

        # Ensure a new instance was created for each process
        self.assertTrue(len(shared_mem) == num_procs)

        # Ensure all the locks are the created instances are unique
        self.assertTrue(len(set(shared_mem.values())) == num_procs)

    def test_creates_new_db(self):
        """
        Tests that a new instance of DB is lazily created when DB() is invoked
        """
        pid = os.getpid()
        before_creation = DBSingletonMeta._instances.copy()  # Dict of DB instances before we call DB()

        with DB() as db:
            pass

        after_creation = DBSingletonMeta._instances

        self.assertTrue(len(after_creation) == len(before_creation) + 1)
        self.assertTrue(pid in after_creation)

    def test_creates_new_db_only_once(self):
        """
        Tests that a DB instance is only created once for each process.
        """
        pid = os.getpid()
        lock1, lock2 = None, None
        before_creation = DBSingletonMeta._instances.copy()  # Dict of DB instances before we call DB()

        with DB() as db:
            lock1 = db.lock

        after_creation1 = DBSingletonMeta._instances.copy()

        self.assertTrue(len(after_creation1) == len(before_creation) + 1)
        self.assertTrue(pid in after_creation1)

        # Invoke a second time ... this should not create anything new, and should return the same lock
        with DB() as db:
            lock2 = db.lock

        after_creation2 = DBSingletonMeta._instances.copy()

        self.assertTrue(len(after_creation1) == len(after_creation2))
        self.assertEqual(lock1, lock2)

    # TODO -- test locking functionality










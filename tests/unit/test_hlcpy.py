import time
from unittest import TestCase
from lamden.hlcpy import HLC

class TestUtilsHLC(TestCase):
    def get_nanoseconds(self):
        hlc = HLC()
        return hlc.get_nanoseconds()

    def test_too_large(self):
        with self.assertRaises(ValueError):
            HLC(2**43 * 1e6, 0)
        HLC((2**43 - 1) * 1e6, 0)
    
        with self.assertRaises(ValueError):
            HLC(2**43 * 1e6 - 1, 2**16)
        HLC(2, 2**16 - 1)


    def test_bin(self):
        h1 = HLC(3e6, 2)
        h2 = HLC.from_bytes(h1.to_bytes())
        self.assertEqual(h2, h1)

        # nanos are not supported in binary representation
        # so reconstructed element should be later than the former
        h1 = HLC(3e5, 4)
        h2 = HLC.from_bytes(h1.to_bytes())
        assert h2 > h1


    def test_str(self):
        h1 = HLC()
        h1.set_nanos(self.get_nanoseconds() + 10e9)
        h2 = HLC.from_str(str(h1))
        self.assertEqual(h2, h1)

        h1 = HLC()
        h1._set(123, 4)
        h2 = HLC.from_str(str(h1))
        self.assertEqual(str(h1).split("_")[1] , '4')
        self.assertEqual(h2, h1)


    def test_compare(self):
        h1 = HLC()
        h2 = HLC()
        h1.set_nanos(self.get_nanoseconds() + 10e9)
        self.assertEqual(h2, h2)
        self.assertLess(h2, h1)


    def test_sync(self):
        future_nanos = self.get_nanoseconds() + 10e9
        print(future_nanos)
        h1 = HLC()
        h1.set_nanos(future_nanos)
        h1.sync()
        nanos, logical = h1.tuple()
        # Logical must have ticked, because nanos
        # should be in the future
        self.assertEqual(logical, 1)
        self.assertEqual(nanos, future_nanos)


    def test_merge(self):
        wall_nanos = self.get_nanoseconds()
        h1 = HLC()
        h1.set_nanos(wall_nanos)
        original_nanos, _ = h1.tuple()
        event = HLC()
        # event is 10 seconds in the future
        event.set_nanos(wall_nanos + 3e9)

        h1.merge(event)
        nanos, logical = h1.tuple()
        self.assertEqual(logical, 1)

        h1.merge(event)
        nanos, logical = h1.tuple()
        self.assertEqual(logical, 2)

        h1.merge(event)
        nanos, logical = h1.tuple()
        self.assertEqual(logical, 3)
        self.assertEqual(original_nanos, wall_nanos)
        self.assertGreater(nanos, wall_nanos + 1000)

        # The wall clock catches up to HLC and resets logical
        time.sleep(4)
        h1.sync()
        _, logical = h1.tuple()
        self.assertEqual(logical, 0)

from unittest import TestCase
from cilantro_ee.nodes.delegate import work
import asyncio


class MockWork:
    def __init__(self, sender):
        self.sender = bytes.fromhex(sender)

    def __eq__(self, other):
        return self.sender == other.sender


class TestWork(TestCase):
    def test_gather_work_waits_for_all(self):
        q = {}

        async def fill_q():
            q['1'] = 123
            await asyncio.sleep(0.1)
            q['3'] = 678
            await asyncio.sleep(0.5)
            q['x'] = 'zzz'

        tasks = asyncio.gather(
            fill_q(),
            work.gather_transaction_batches(q, expected_batches=3, timeout=5)
        )

        loop = asyncio.get_event_loop()
        _, w = loop.run_until_complete(tasks)

        expected = [123, 678, 'zzz']

        self.assertListEqual(expected, w)

    def test_gather_past_timeout_returns_current_work(self):
        q = {}

        async def fill_q():
            q['1'] = 123
            await asyncio.sleep(0.1)
            q['3'] = 678
            await asyncio.sleep(1.1)
            q['x'] = 'zzz'

        tasks = asyncio.gather(
            fill_q(),
            work.gather_transaction_batches(q, expected_batches=3, timeout=1)
        )

        loop = asyncio.get_event_loop()
        _, w = loop.run_until_complete(tasks)

        expected = [123, 678]

        self.assertListEqual(expected, w)

    def test_pad_work_does_nothing_if_complete(self):
        expected_masters = ['ab', 'cd', '23', '45']

        work_list = [MockWork('ab'), MockWork('cd'), MockWork('23'), MockWork('45')]
        expected_list = [MockWork('ab'), MockWork('cd'), MockWork('23'), MockWork('45')]

        work.pad_work(work_list, expected_masters=expected_masters)

        self.assertListEqual(work_list, expected_list)

    def test_pad_work_adds_tx_batches_if_missing_masters(self):
        expected_masters = ['ab', 'cd', '23', '45']

        work_list = [MockWork('ab'), MockWork('cd')]

        work.pad_work(work_list, expected_masters=expected_masters)

        a, b, c, d = work_list

        self.assertEqual(a, MockWork('ab'))
        self.assertEqual(b, MockWork('cd'))
        self.assertEqual(c.sender.hex(), "23")
        self.assertEqual(c.inputHash, "23")
        self.assertEqual(d.sender.hex(), '45')
        self.assertEqual(d.inputHash, "45")


from unittest import TestCase
from lamden.nodes.queue_base import ProcessingQueue

import time
import asyncio

class TestProcessingQueue(TestCase):
    def setUp(self):
        self.processing_queue = ProcessingQueue()

    def tearDown(self):
        self.processing_queue.stop()
        self.processing_queue.flush()

    async def await_queue_stopping(self):
        print (self.processing_queue.currently_processing)
        # Await the stopping of the queue
        await self.processing_queue.stopping()

    async def delay_processing(self, func, delay):
        print('\n')
        print('Starting Sleeping: ', time.time())
        await asyncio.sleep(delay)
        print('Done Sleeping: ', time.time())
        if func:
            return func()

    def stop(self):
        self.running = False

    def test_can_start(self):
        self.processing_queue.start()
        self.assertEqual(self.processing_queue.running, True)

    def test_can_stop(self):
        self.processing_queue.stop()
        self.assertEqual(self.processing_queue.running, False)

    def test_can_start_processing(self):
        self.processing_queue.start_processing()
        self.assertEqual(self.processing_queue.currently_processing, True)

    def test_can_stop_processing(self):
        self.processing_queue.stop_processing()
        self.assertEqual(self.processing_queue.currently_processing, False)

    def test_can_await_stopping(self):
        # Mark the queue as currently processing
        self.processing_queue.start_processing()

        # Stop the queue
        self.processing_queue.stop()

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.await_queue_stopping(),
            self.delay_processing(func=self.processing_queue.stop_processing, delay=2)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        # Assert the queue is stopped and not processing any transactions
        self.assertEqual(self.processing_queue.currently_processing, False)
        self.assertEqual(self.processing_queue.running, False)


    def test_flush(self):
        # Add a bunch of transactions to the queue
        for i in range(10):
            self.processing_queue.queue.append("testing")

        # assert queue has items in it
        self.assertEqual(len(self.processing_queue), 10)

        # flush queue
        self.processing_queue.flush()

        # Assert queue is empty
        self.assertEqual(len(self.processing_queue), 0)

    def test_is_subscriptable(self):
        item = "testing"

        self.processing_queue.append(item)

        # assert queue has items in it
        self.assertEqual("testing", self.processing_queue[0])

    def test_is_subscriptable_ret_None_if_indexError(self):
        # assert queue has items in it
        self.assertIsNone(self.processing_queue[0])

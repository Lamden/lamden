from unittest import TestCase
from lamden.nodes.filequeue import FileQueue
from tests.integration.mock.create_directories import create_fixture_directories, remove_fixture_directories

import time
import asyncio


class TestProcessingQueue(TestCase):
    def setUp(self):
        #self.fixture_directories = ['txq']
        #create_fixture_directories(dir_list=self.fixture_directories)

        self.tx_queue = FileQueue(root="./.lamden/file_queue_test/txq")

    def tearDown(self):
        pass
        remove_fixture_directories(root='./.lamden/file_queue_test', dir_list=['txq'])

    def test_append_tx(self):
        pass


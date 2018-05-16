from cilantro.messages import NewBlockNotification
from unittest import TestCase


class NewBlockNotificationTests(TestCase):

    def test_serialization(self):
        """
        Tests serialize and from_bytes are inverse operations
        """
        block_hash = 'A' * 64
        block_num = 4839

        bn = NewBlockNotification.create(new_block_hash=block_hash, new_block_num=block_num)
        bn_binary = bn.serialize()

        bn_clone = NewBlockNotification.from_bytes(bn_binary)

        self.assertEqual(bn_clone, bn)


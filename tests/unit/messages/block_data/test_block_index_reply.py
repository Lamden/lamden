from cilantro_ee.messages.block_data.state_update import BlockIndexReply
from unittest import TestCase


class TestBlockIndexReply(TestCase):

    def _build_reply(self, return_data=False):
        mn1 = 'ABCD' * 16
        mn2 = 'DCBA' * 16
        mn3 = 'AABB' * 16

        b1 = 'A' * 64
        b2 = 'B' * 64
        b3 = 'C' * 64

        data = [[b1, 1, [mn1,]], [b2, 2, [mn2, mn1]], [b3, 3, [mn1, mn2, mn3]]]
        if return_data:
            return BlockIndexReply.create(data), data
        else:
            return BlockIndexReply.create(data)

    def test_create(self):
        reply, data = self._build_reply(return_data=True)
        self.assertEqual(reply.indices, data)

    def test_create_with_empty(self):
        reply = BlockIndexReply.create([])
        self.assertEqual(reply.indices, [])

    def test_serialization(self):
        reply = self._build_reply()
        self.assertEqual(reply, BlockIndexReply.from_bytes(reply.serialize()))

from cilantro.messages import BlockMetaData
from unittest import TestCase


class TestBlockMetaData(TestCase):

    def test_create(self):
        # TODO implement .. create the object with args, and assert object.property equals expected value
        pass

    def test_validate(self):
        # TODO implement ... multiple test for various validation failures
        pass

    def test_serialize_deserialize(self):
        req = BlockMetaData.create()  # TODO add appropriate args here
        clone = BlockMetaData.from_bytes(req.serialize())

        self.assertEquals(clone, req)
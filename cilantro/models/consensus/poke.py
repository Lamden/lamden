from cilantro.models import ModelBase


class Poke(ModelBase):
    name = "POKE"

    def validate(self):
        pass

    def deserialize_struct(cls, data: bytes):
        # We are assuming data is an encoded string here
        return data.decode()

    @staticmethod
    def create():
        return Poke('')

    def serialize(self):
        # We are assuming _data is a string
        assert self._data is not None, "attempted to serialize poke without _data set"
        assert type(self._data) is str, "attempted to serialize poke but _data is not a string"
        return self._data.encode()

    @property
    def sender_url(self):
        return self._data

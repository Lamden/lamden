from cilantro.messages import MessageBase
import json
from cilantro import Constants


class MerkleSignature(MessageBase):
    """
    _data is a dict with keys: 'signature', 'timestamp', 'sender'
    """
    name = "MERKLE_SIGNATURE"

    SIG = 'signature'
    TS = 'timestamp'
    SENDER = 'sender'

    def validate(self):
        assert type(self._data) == dict, "_data is not a dictionary"
        assert self.SIG in self._data, "Signature field missing from _data: {}".format(self._data)
        assert self.TS in self._data, "Timestamp field missing from _data: {}".format(self._data)
        assert self.SENDER in self._data, "Sender field missing from _data: {}".format(self._data)

    def serialize(self):
        return json.dumps(self._data).encode()

    def verify(self, msg, verifying_key):
        # TODO validate verifying key and signature (hex, 64 char)
        return Constants.Protocol.Wallets.verify(verifying_key, msg, self.signature)

    @classmethod
    def from_fields(cls, sig_hex: str, timestamp: str, sender: str, validate=True):
        data = {cls.SIG: sig_hex, cls.TS: timestamp, cls.SENDER: sender}
        return cls.from_data(data, validate=validate)

    @classmethod
    def deserialize_data(cls, data: bytes):
        return json.loads(data.decode())

    @property
    def signature(self):
        return self._data[self.SIG]

    @property
    def timestamp(self):
        return self._data[self.TS]

    @property
    def sender(self):
        return self._data[self.SENDER]


class BlockContender(MessageBase):
    """
    _data is a dict with keys:
        'signature': [MerkleSignature1, MerkleSignature2, MerkleSignature3, ....]
            (all entries are MerkleSignature objects)
        'nodes': [root hash, root left hash, root right hash, root left left hash ... ]
            (all entries are hex strings)
    """
    name = "BLOCK_CONTENDER"

    SIGS = 'signature'
    NODES = 'nodes'

    def validate(self):
        pass

    def serialize(self):
        # TODO -- implement
        # loop through signatures list, serialize each
        # json dump entire _data
        pass

    @classmethod
    def deserialize_data(cls, data: bytes):
        # TODO -- implement
        # json loads entire data
        # deserialize each signature
        pass

    @property
    def signatures(self):
        return self._data[self.SIGS]

    @property
    def nodes(self):
        return self._data[self.NODES]
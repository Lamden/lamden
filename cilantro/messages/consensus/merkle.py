from cilantro import Constants
from cilantro.messages import MessageBase, TransactionBase
from cilantro.protocol.structures import MerkleTree
import json
import pickle


class MerkleSignature(MessageBase):
    """
    _data is a dict with keys: 'signature', 'timestamp', 'sender'
    """
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
    def create(cls, sig_hex: str, timestamp: str, sender: str, validate=True):
        data = {cls.SIG: sig_hex, cls.TS: timestamp, cls.SENDER: sender}
        return cls.from_data(data, validate=validate)

    @staticmethod
    def do_this():
        print("done")

    @classmethod
    def _deserialize_data(cls, data: bytes):
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
        'nodes': is a list of hashes of leaves
    """
    SIGS = 'signature'
    NODES = 'nodes'

    def validate(self):
        pass

    def serialize(self):
        # loop through signatures list, serialize each
        # json dump entire _data
        for i in range(len(self._data[self.SIGS])):
            self._data[self.SIGS][i] = self._data[self.SIGS][i].serialize()
        return pickle.dumps(self._data)

    @classmethod
    def create(cls, signatures: list, nodes: list):
        data = {cls.SIGS: signatures, cls.NODES: nodes}
        return cls.from_data(data)

    @classmethod
    def _deserialize_data(cls, data: bytes):
        # TODO -- implement
        # json loads entire data
        # deserialize each signature
        data = pickle.loads(data)
        for i in range(len(data[cls.SIGS])):
            data[cls.SIGS][i] = MerkleSignature.from_bytes(data[cls.SIGS][i])
        return data

    @property
    def signatures(self):
        return self._data[self.SIGS]

    @property
    def nodes(self):
        return self._data[self.NODES]


class BlockDataRequest(MessageBase):
    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data

    def serialize(self):
        return self._data

    @classmethod
    def create(cls, tx_hash: bytes):
        return cls.from_data(tx_hash)

    @property
    def tx_hash(self):
        return self._data


class BlockDataReply(MessageBase):
    """
    Underlying _data is just a binary blob storing a serialized transaction
    """
    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data

    def serialize(self):
        return self._data

    @classmethod
    def create(cls, tx_binary: bytes):
        return cls.from_data(tx_binary)

    @property
    def raw_tx(self):
        return self._data

    @property
    def tx_hash(self):
        return MerkleTree.hash(self._data)



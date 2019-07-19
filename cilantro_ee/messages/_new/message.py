import capnp

blockdata_capnp = capnp.load('../capnp/blockdata.capnp')
subblock_capnp = capnp.load('../capnp/subblock.capnp')
envelope_capnp = capnp.load('../capnp/envelope.capnp')
transaction_capnp = capnp.load('../capnp/transaction.capnp')

CLASS_TO_TYPE_MAP = {
    blockdata_capnp.BlockData: 0,
    blockdata_capnp.BlockMetaData: 1,
    blockdata_capnp.StateUpdateReply: 2,
    blockdata_capnp.StateUpdateRequest: 3,
    envelope_capnp.Envelope: 4,
    envelope_capnp.MessageMeta: 5,
    envelope_capnp.Seal: 6,
    subblock_capnp.AlignInputHash: 7,
    subblock_capnp.SubBlock: 8,
    subblock_capnp.SubBlockContender: 9,
    transaction_capnp.ContractPayload: 10,
    transaction_capnp.ContractTransaction: 11,
    transaction_capnp.MetaData: 12,
    transaction_capnp.OrderingContainer: 13,
    transaction_capnp.PublishTransaction: 14,
    transaction_capnp.StandardTransaction: 15,
    transaction_capnp.TransactionBatch: 16,
    transaction_capnp.TransactionContainer: 17,
    transaction_capnp.TransactionData: 18,
    transaction_capnp.Transactions: 19
}

TYPE_TO_CLASS_MAP = {
    0: blockdata_capnp.BlockData,
    1: blockdata_capnp.BlockMetaData,
    2: blockdata_capnp.StateUpdateReply,
    3: blockdata_capnp.StateUpdateRequest,
    4: envelope_capnp.Envelope,
    5: envelope_capnp.MessageMeta,
    6: envelope_capnp.Seal,
    7: subblock_capnp.AlignInputHash,
    8: subblock_capnp.SubBlock,
    9: subblock_capnp.SubBlockContender,
    10: transaction_capnp.ContractPayload,
    11: transaction_capnp.ContractTransaction,
    12: transaction_capnp.MetaData,
    13: transaction_capnp.OrderingContainer,
    14: transaction_capnp.PublishTransaction,
    15: transaction_capnp.StandardTransaction,
    16: transaction_capnp.TransactionBatch,
    17: transaction_capnp.TransactionContainer,
    18: transaction_capnp.TransactionData,
    19: transaction_capnp.Transactions
}


def deserialize_msg(frames):
    msg_type = frames[0]
    msg_blob = frames[1]

    builder = TYPE_TO_CLASS_MAP[msg_type]
    obj = builder.from_bytes_packed(msg_blob)

    return obj

import capnp

blockdata_capnp = capnp.load('../capnp/blockdata.capnp')
subblock_capnp = capnp.load('../capnp/subblock.capnp')
envelope_capnp = capnp.load('../capnp/envelope.capnp')
transaction_capnp = capnp.load('../capnp/transaction.capnp')

# Message type registration
# Each type is a uint32 number (0 - 4294967295)
#     0 -  9999 = block data
# 10000 - 19999 = envelope
# 20000 - 29999 = transaction
# 30000 - 39999 = signals
# 40000 - 49999 = consensus


class Signals:
    MAKE_NEXT_BLOCK = 30000
    PENDING_TRANSACTIONS = 30001
    NO_TRANSACTIONS = 30002
    HALT = 30003
    EMPTY_BLOCK_MADE = 30004
    NON_EMPTY_BLOCK_MADE = 30005
    READY = 30006
    POKE = 30007
    UPDATED_STATE_SIGNAL = 30008


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
    transaction_capnp.TransactionBatch: 16,
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
    16: transaction_capnp.TransactionBatch,
    18: transaction_capnp.TransactionData,
    19: transaction_capnp.Transactions
}


def deserialize_msg(frames):
    msg_type = frames[0]
    msg_blob = frames[1]

    builder = TYPE_TO_CLASS_MAP[msg_type]
    obj = builder.from_bytes_packed(msg_blob)

    return obj

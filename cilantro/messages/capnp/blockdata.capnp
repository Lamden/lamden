@0xc9a01417cf45e892;

using T = import "transaction.capnp";

struct FullBlockMetaData {
    blockHash @0 :Data;
    merkleRoots @1 :List(Data);
    prevBlockHash @2 :Data;
    timestamp @3 :UInt64;
    masternodeSignature @4 :Data;
    blockNum @5 :UInt32;
}

struct BlockMetaData {
    blockHash @0 :Data;
    merkleRoots @1 :List(Data);
    prevBlockHash @2 :Data;
    timestamp @3 :UInt64;
    masternodeSignature @4 :Data;
}

struct BlockData {
    blockHash @0 :Data;
    blockNum @1 :UInt32;
    merkleRoots @2 :List(Data);
    prevBlockHash @3 :Data;
    masternodeSignature @4 :Data;
    transactions @5 :List(Data);
}

struct StateUpdateRequest {
    blockHash @0 :Data;
}

struct OldBlockMetaData {
    # Hash of the block
    hash @0 :Data;

    # BlockData fields (see BLOCK_DATA_COLS in db/blocks.py)
    merkleRoot @1 :Data;
    merkleLeaves @2 :Data;
    prevBlockHash @3 :Data;
    timestamp @4 :UInt64;
    masternodeSignature @5 :Data;
    masternodeVk @6 :Data;
    blockContender @7 :Data;
}

struct BlockMetaDataReply {
    blocks :union {
        isLatest @0 :Void;
        data @1 :List(OldBlockMetaData);
    }
}

struct BlockMetaDataRequest {
    currentBlockHash @0 :Data;
}

struct StateUpdateReply {
    blockData @0 :List(BlockMetaData);
}

struct TransactionRequest {
    transactions @0: List(Data);  # List of transaction hashes
}


struct TransactionReply {
    transactions @0: List(Data);  # List of transaction binaries
}

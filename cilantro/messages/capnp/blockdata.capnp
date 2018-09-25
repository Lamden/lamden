@0xa61eafaff944c2b3;

struct BlockMetaData {
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

struct FullBlockMetaData {
    blockHash @0 :Data;
    merkleRoots @1 :List(Data);
    prevBlockHash @2 :Data;
    timestamp @3 :UInt64;
    masternodeSignature @4 :Data;
    transactions @5 :List(Data);
}

struct BlockMetaDataReply {
    blocks :union {
        isLatest @0 :Void;
        data @1 :List(BlockMetaData);
    }
}

struct BlockMetaDataRequest {
    currentBlockHash @0 :Data;
}

struct StateUpdateReply {
    blockData @0 :List(FullBlockMetaData);
}

struct TransactionRequest {
    transactions @0: List(Data);  # List of transaction hashes
}


struct TransactionReply {
    transactions @0: List(Data);  # List of transaction binaries
}

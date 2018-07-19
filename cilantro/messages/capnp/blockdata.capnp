@0xa61eafaff944c2b3;


struct BlockMetaData {
    # Hash of the block
    hash @0 :Data;

    # BlockData fields (see BLOCK_DATA_COLS in db/blocks.py)
    merkleRoot @1 :Data;
    merkleLeaves @2 :List(Data);
    prevBlockHash @3 :Data;
    timestamp @4 :UInt64;
    masternodeSignature @5 :Data;
    masternodeVk @6 :Data;
    blockContender @7 :Data;
}


struct BlockMetaDataReply {
    blocks :union {
        unset @0 :Void;
#        data @1 :List(BlockMetaData);
        data @1 :List(Data);
    }
}


struct BlockMetaDataRequest {
    currentBlockHash @0 :Data;
}


struct TransactionRequest {
    transactions @0: List(Data);  # List of transaction hashes
}


struct TransactionReply {
    transactions @0: List(Data);  # List of transaction binaries
}



@0xc9a01417cf45e892;

using T = import "transaction.capnp";

struct BlockMetaData {
    blockHash @0 :Data;
    merkleRoots @1 :List(Data);
    inputHashes @2 :List(Data);
    prevBlockHash @3 :Data;
    timestamp @4 :UInt64;
    masternodeSignature @5 :Data;
    blockNum @6 :UInt32;
}

struct BlockData {
    blockHash @0 :Data;
    blockNum @1 :UInt32;
    merkleRoots @2 :List(Data);
    inputHashes @3 :List(Data);
    prevBlockHash @4 :Data;
    masternodeSignature @5 :Data;
    transactions @6 :List(Data);
}

struct StateUpdateRequest {
    blockHash @0 :Data;
}

struct StateUpdateReply {
    blockData @0 :BlockData;
}

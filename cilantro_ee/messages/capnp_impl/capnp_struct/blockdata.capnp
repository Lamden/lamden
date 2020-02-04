@0xc9a01417cf45e892;

using SB = import "subblock.capnp";


struct BlockMetaData {
    blockHash @0 :Data;
    merkleRoots @1 :List(Data);
    inputHashes @2 :List(Data);
    prevBlockHash @3 :Data;
    timestamp @4 :UInt64;
    blockOwners @5 :List(Text);
    blockNum @6 :UInt32;
}


struct BlockData {
    blockHash @0 :Data;
    blockNum @1 :UInt32;
    blockOwners @2 :List(Data);
    prevBlockHash @3 :Data;
    subBlocks @4 :List(SB.SubBlock);
}

struct BlockIndexRequest {
    blockHash @0 :Data;
    sender @1 :Data;
}

struct BlockDataRequest {
    blockNum @0 :UInt32;
}

struct BlockIndex {
    blockNum @0 :UInt32;
    blockHash @1 :Data;
    blockOwners @2 :List(Data);
}

struct BlockIndexReply {
    indices @0 :List(BlockIndex);
}

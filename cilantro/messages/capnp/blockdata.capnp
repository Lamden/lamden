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
    blockHash @0 :Text;
    blockNum @1 :UInt32;
    blockOwners @2 :List(Text);
    prevBlockHash @3 :Text;
    subBlocks @4 :List(SB.SubBlock);
}


struct StateUpdateRequest {
    blockHash @0 :Data;
}


struct StateUpdateReply {
    blockData @0 :BlockData;
}

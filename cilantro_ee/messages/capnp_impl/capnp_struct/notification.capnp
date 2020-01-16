@0xc9b01417cf45e892;

using S = import "subblock.capnp";

struct BlockNotification {
    blockNum @0 :UInt32;
    blockHash @1 :Data;
    prevBlockHash @2 :Data;
    blockOwners @3 :List(Text);
    subBlockNum @4 :List(List(UInt32));
    inputHashes @5 :List(List(Data));
    union {
      failedBlock @6 :Void;
      newBlock @7 :Void;
      emptyBlock @8 :Void;
      partialBlock @9 :Void;
    }
    subBlocks @10 :List(S.SubBlock);
}

struct BurnInputHashes {
    subBlockNum @0 :List(UInt32);
    inputHashes @1: List(Data);
}

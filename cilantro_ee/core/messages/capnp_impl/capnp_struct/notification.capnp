@0xc9b01417cf45e892;

struct BlockNotification {
    blockNum @0 :UInt32;
    blockHash @1 :Data;
    blockOwners @2 :List(Text);
    subBlockNum @3 :List(List(UInt32));
    inputHashes @4 :List(List(Data));
    union {
      failedBlock @5 :Void;
      newBlock @6 :Void;
      emptyBlock @7 :Void;
      partialBlock @8 :Void;
    }
}

struct BurnInputHashes {
    subBlockNum @0 :List(UInt32);
    inputHashes @1: List(Data);
}

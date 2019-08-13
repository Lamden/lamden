@0xc9b01417cf45e892;

# crp do we need prevBlockHash ??
struct BlockNotification {
    blockNum @0 :UInt32;
    blockHash @1 :Data;
    blockOwners @2 :List(Text);
    firstSbIdx @3 :UInt32;
    inputHashes @4 :List(List(Text));
    type :union  {
      failedBlock @5 :Void;
      newBlock @6 :Void;
      emptyBlock @7 :Void;
      partialBlock @8 :Void;
    }
}

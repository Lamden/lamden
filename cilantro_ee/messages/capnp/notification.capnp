@0xc9b01417cf45e892;


struct ConsensusBlockNotification {
    prevBlockHash @0 :Text;
    blockHash @1 :Text;
    blockNum @2 :UInt32;
    firstSbIdx @3 :UInt32;
    blockOwners @4 :List(Text);
    inputHashes @5 :List(Data);
}


struct FailedBlockNotification {
    prevBlockHash @0 :Text;
    blockHash @1 :Text;
    blockNum @2 :UInt32;
    firstSbIdx @3 :UInt32;
    inputHashes @4 :List(List(Text));
}

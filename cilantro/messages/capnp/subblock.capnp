@0xab5e7866e64c6d4d;

using T = import "transaction.capnp";

struct SubBlock {
    merkleRoot @0 :Text;
    signatures @1: List(Data);
    merkleLeaves @2: List(Text);
    subBlockIdx @3: UInt8;
    inputHash @4: Text;
}

struct SubBlockContender {
    resultHash @0 :Data;
    inputHash @1 :Data;
    merkleLeaves @2: List(Data);
    signature @3 :Data;
    transactions @4: List(Data);
    subBlockIdx @5: UInt8;
    prevBlockHash @6: Text;
}

struct EmptySubBlockContender {
    inputHash @0 :Data;
    signature @1 :Data;
    subBlockIdx @2 :UInt8;
}


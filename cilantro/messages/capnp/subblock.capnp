@0xab5e7866e64c6d4d;

using T = import "transaction.capnp";


# SubBlock is intended to be nested inside of BlockData, and never really used on its own
struct SubBlock {
    merkleRoot @0 :Text;
    signatures @1 :List(Data);
    merkleLeaves @2 :List(Text);
    subBlockIdx @3 :UInt8;
    inputHash @4 :Text;
    transactions @5 :List(T.TransactionData);
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


struct AlignInputHash {
    inputHash @0 :Data;
}

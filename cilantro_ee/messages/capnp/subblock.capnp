@0xab5e7866e64c6d4d;

using T = import "transaction.capnp";

# SubBlock is intended to be nested inside of BlockData, and never really used on its own

struct MerkleProof {
    hash @0 :Data;
    signer @1: Data;
    signature @2: Data;
}

struct SubBlock {
    merkleRoot @0 :Data;
    signatures @1 :List(Data);
    merkleLeaves @2 :List(Text);
    subBlockIdx @3 :UInt8;
    inputHash @4 :Data;
    transactions @5 :List(T.TransactionData);
}

struct SubBlockContender {
    resultHash @0 :Data;
    inputHash @1 :Data;
    merkleLeaves @2: List(Data);
    signature @3 :Data;
    transactions @4: List(Data);
    subBlockIdx @5: UInt8;
    prevBlockHash @6: Data;
}

struct AlignInputHash {
    inputHash @0 :Data;
    sbIndex @1: UInt8;
}

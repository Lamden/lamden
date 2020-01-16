@0xab5e7866e64c6d4d;

using T = import "transaction.capnp";

# SubBlock is intended to be nested inside of BlockData, and never really used on its own
# todo - remove hash from MerkleProof - it is same as MerkleRoot at higher level
#      - remove inputHash from SubBlock
#      - include SubBlock as part of SubBlockContender with additional fields: prevBlockHash and inputHash

struct MerkleProof {
    hash @0 :Data;
    signer @1: Data;
    signature @2: Data;
}

struct SubBlock {
    merkleRoot @0 :Data;
    signatures @1 :List(Data);
    merkleLeaves @2 :List(Data);
    subBlockNum @3 :UInt8;
    inputHash @4 :Data;
    transactions @5 :List(T.TransactionData);
}

struct SubBlockContender {
    resultHash @0 :Data;
    inputHash @1 :Data;
    merkleLeaves @2: List(Data);
    signature @3 :Data;
    transactions @4: List(Data);
    subBlockNum @5: UInt8;
    prevBlockHash @6: Data;
}

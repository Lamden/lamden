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

struct Signature {
    signer @0: Data;
    signature @1 :Data;
}

struct MerkleTree {
    leaves @0 :List(Data);
    signature @1 :Data;
}

struct SubBlock {
    merkleRoot @0 :Data;
    signatures @1 :List(Data);
    merkleLeaves @2 :List(Data);
    subBlockNum @3 :UInt8;
    inputHash @4 :Data;
    transactions @5 :List(T.TransactionData);
}

struct NewSubBlock {
    inputHash @0: Data;
    transactions @1: List(T.TransactionData);
    merkleTree @2: MerkleTree;
    signatures @3: List(Signature);
    subBlockNum @4: UInt8;
    prevBlockHash @5: Data;
}

struct SubBlockContender {
    inputHash @0 :Data;
    transactions @1: List(T.TransactionData);
    merkleTree @2 :MerkleTree;
    signer @3 :Data;
    subBlockNum @4: UInt8;
    prevBlockHash @5: Data;
}

struct SubBlockContenders {
    contenders @0 :List(SubBlockContender);
}
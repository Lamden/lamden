@0xab5e7866e64c6d4d;

struct SubBlockContender {
    resultHash @0 :Data;
    inputHash @1 :Data;
    merkleLeaves @2: List(Data);
    signature @3 :Data;
    transactions @4: List(Data);
}

struct FullBlockHash {
    fullBlockHash @0 :Data;
}

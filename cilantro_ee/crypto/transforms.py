# If a subblock fails, how do we serialize it?
# For now, fuck it. It's going to be a strange format
# In the future, as long as everyone agrees upon the tx inputs, then the block should include these and note it was a
# failure. Then the masternode can try sending it again.


# struct SubBlock {
#     merkleRoot @0 :Data;
#     signatures @1 :List(Data);
#     merkleLeaves @2 :List(Data);
#     subBlockNum @3 :UInt8;
#     inputHash @4 :Data;
#     transactions @5 :List(T.TransactionData);
# }
#
# struct SubBlockContender {
#     inputHash @0 :Data;
#     transactions @1: List(T.TransactionData);
#     merkleTree @2 :MerkleTree;
#     signer @3 :Data;
#     subBlockNum @4: UInt8;
#     prevBlockHash @5: Data;
# }

# struct BlockData {
#     blockHash @0 :Data;
#     blockNum @1 :UInt32;
#     blockOwners @2 :List(Data);
#     prevBlockHash @3 :Data;
#     subBlocks @4 :List(SB.SubBlock);
# }

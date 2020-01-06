def subblock_contender_list_to_block(sbcs):

    pass

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

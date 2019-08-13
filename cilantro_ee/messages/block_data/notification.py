import capnp
import notification_capnp

class BlockNotification:
    @staticmethod
    def get_block_notification(block_num, block_hash, block_owners, first_sb_idx, input_hashes):
        bn = notification_capnp.BlockNotification.new_message()
        bn.blockNum = block_num
        bn.blockHash = block_hash
        bn.blockOwners = [bo for bo in block_owners]
        bn.firstSbIdx = first_sb_idx
        bn.inputHashes = [[ih for ih in ihes] for ihes in input_hashes]
        return bn

    @staticmethod
    def get_failed_block_notification(block_num, block_hash, block_owners, first_sb_idx, input_hashes):
        bn = BlockNotification.get_block_notification(block_num, block_hash,
                                     block_owners, first_sb_idx, input_hashes)
        bn.type.failedBlock = None
        return bn.to_bytes_packed()

    @staticmethod
    def get_new_block_notification(block_num, block_hash, block_owners, first_sb_idx, input_hashes):
        bn = BlockNotification.get_block_notification(block_num, block_hash,
                      block_owners, first_sb_idx, [[ih] for ih in input_hashes])
        bn.type.newBlock = None
        return bn.to_bytes_packed()

    @staticmethod
    def get_empty_block_notification(block_num, block_hash, first_sb_idx, input_hashes):
        bn = BlockNotification.get_block_notification(block_num, block_hash,
                      [], first_sb_idx, [[ih] for ih in input_hashes])
        bn.type.emptyBlock = None
        return bn.to_bytes_packed()

    @staticmethod
    def get_partial_block_notification(block_num, block_hash, block_owners, first_sb_idx, input_hashes):
        bn = BlockNotification.get_block_notification(block_num, block_hash,
                      block_owners, first_sb_idx, [[ih] for ih in input_hashes])
        bn.type.partialBlock = None
        return bn.to_bytes_packed()

    @staticmethod
    def unpack_block_notification(msg):
        return notification_capnp.BlockNotification.from_bytes_packed(msg)


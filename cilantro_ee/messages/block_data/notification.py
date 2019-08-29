import capnp
import notification_capnp
import hashlib

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
    def get_block_hash(prev_block_hash, input_hashes):
        if type(prev_block_hash) == str:
            prev_block_hash = bytes.fromhex(prev_block_hash)

        h = hashlib.sha3_256()
        h.update(prev_block_hash)
        for ihes in input_hashes:
            for ih in ihes:
                h.update(bytes.fromhex(ih) if type(ih) == str else ih)
        return h.digest()

    @staticmethod
    def get_failed_block_notification(block_num, prev_block_hash,
                                      first_sb_idx, input_hashes):
        block_hash = BlockNotification.get_block_hash(prev_block_hash, input_hashes)
        bn = BlockNotification.get_block_notification(block_num, block_hash, [],
                                                     first_sb_idx, input_hashes)
        bn.type.failedBlock = None
        return bn

    @staticmethod
    def get_new_block_notification(block_num, block_hash, block_owners, first_sb_idx, input_hashes):
        bn = BlockNotification.get_block_notification(block_num, block_hash,
                      block_owners, first_sb_idx, [[ih] for ih in input_hashes])
        bn.type.newBlock = None
        return bn

    @staticmethod
    def get_empty_block_notification(block_num, prev_block_hash, first_sb_idx, input_hashes):
        input_hashes = [[ih] for ih in input_hashes]
        block_hash = BlockNotification.get_block_hash(prev_block_hash, input_hashes)
        bn = BlockNotification.get_block_notification(block_num, block_hash, [],
                                                      first_sb_idx, input_hashes)
        bn.type.emptyBlock = None
        return bn

    # todo - needs more details on which sbs' are used to make partial block
    @staticmethod
    def get_partial_block_notification(block_num, block_hash, block_owners, first_sb_idx, input_hashes):
        bn = BlockNotification.get_block_notification(block_num, block_hash,
                      block_owners, first_sb_idx, [[ih] for ih in input_hashes])
        bn.type.partialBlock = None
        return bn

    @staticmethod
    def pack_block_notification(block):
        return block.to_bytes_packed()

    @staticmethod
    def unpack_block_notification(msg):
        return notification_capnp.BlockNotification.from_bytes_packed(msg)


class BurnInputHashes:
    @staticmethod
    def get_burn_input_hashes_packed(input_hashes):
        return notification_capnp.BurnInputHashes.new_message(
                      inputHashes=[ih for ih in input_hashes]).to_bytes_packed()

    @staticmethod
    def unpack_burn_input_hashes(msg):
        return notification_capnp.BurnInputHashes.from_bytes_packed(msg)


import hashlib

class BlockNotification:
    # raghu todo - this function should go into utils or hash utils?
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

    # todo - needs more details on which sbs' are used to make partial block
    @staticmethod
    def get_partial_block_notification(block_num, block_hash, block_owners, first_sb_idx, input_hashes):
        # bn = BlockNotification.get_block_notification(block_num, block_hash,
                      # block_owners, first_sb_idx, [[ih] for ih in input_hashes])
        # bn.type.partialBlock = None
        # return bn
        pass



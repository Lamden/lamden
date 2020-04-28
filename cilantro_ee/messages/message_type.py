from enum import IntEnum, auto, unique

@unique
class MessageBaseType(IntEnum):
    def _generate_next_value_(name, start, count, last_values):
        assert count < 128, "Exceeds the maximum supported message types"
        return 2 * count


class MessageType(MessageBaseType):
    SIGNED_MESSAGE = 0

    MAKE_NEXT_SB = auto()
    COMMIT_CUR_SB = auto()
    DISCORD_AND_ALIGN = auto()

    PENDING_TRANSACTIONS = auto()
    NO_TRANSACTIONS = auto()
    READY = auto()

    SUBBLOCK_CONTENDER = auto()
    SUBBLOCK_CONTENDERS = auto()

    BLOCK_INDEX_REQUEST = auto()
    BLOCK_INDEX_REPLY = auto()
    BLOCK_DATA_REQUEST = auto()
    BLOCK_DATA_REPLY = auto()
    BLOCK_DATA = auto()
    BLOCK_NOTIFICATION = auto()
    BURN_INPUT_HASHES = auto()

    NEW_BLOCK_AND_WORK = auto()

    TRANSACTION_BATCH = auto()
    # todo - need a better way to handle internal messages inside another message
    TRANSACTION_DATA = auto()
    MERKLE_PROOF = auto()
    TRANSACTION = auto()
    SUBBLOCK = auto()

    LATEST_BLOCK_HEIGHT_REQUEST = auto()
    LATEST_BLOCK_HEIGHT_REPLY = auto()

    LATEST_BLOCK_HASH_REQUEST = auto()
    LATEST_BLOCK_HASH_REPLY = auto()

    BAD_REQUEST = auto()

    IP_FOR_VK_REQUEST = auto()
    IP_FOR_VK_REPLY = auto()

    ACKNOWLEDGED = auto()

    UPDATE_REG_TRIGGER = auto()
    UPDATE_REG_VOTE = auto()
    UPDATE_REG_RDY = auto()


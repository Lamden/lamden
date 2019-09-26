from enum import IntEnum, auto, unique

@unique
class MessageBaseType(IntEnum):
    def _generate_next_value_(name, start, count, last_values):
        assert count < 128, "Exceeds the maximum supported message types"
        return 2 * count



class MessageType(MessageBaseType):
    SIGNED_MESSAGE = 0

    MAKE_NEXT_BLOCK = auto()
    PENDING_TRANSACTIONS = auto()
    NO_TRANSACTIONS = auto()
    READY = auto()

    SUBBLOCK_CONTENDER = auto()
    BLOCK_INDEX_REQUEST = auto()
    BLOCK_INDEX_REPLY = auto()
    BLOCK_DATA_REQUEST = auto()
    BLOCK_DATA_REPLY = auto()
    BLOCK_NOTIFICATION = auto()
    BURN_INPUT_HASHES = auto()

    TRANSACTION_BATCH = auto()

    LATEST_BLOCK_HEIGHT_REQUEST = auto()
    LATEST_BLOCK_HEIGHT_REPLY = auto()


from enum import Enum, unique


@unique
class MessageType(Enum):
    SIGNED_MESSAGE = b'\x00'

    MAKE_NEXT_BLOCK = b'\x01'
    PENDING_TRANSACTIONS = b'\x02'
    NO_TRANSACTIONS = b'\x03'
    READY = b'\x04'

    SUBBLOCK_CONTENDER = b'\x0a'
    BLOCK_INDEX_REQUEST = b'\x0b'
    BLOCK_INDEX_REPLY = b'\x0d'
    BLOCK_DATA_REQUEST = b'\x0e'
    BLOCK_DATA_REPLY = b'\x0f'
    BLOCK_NOTIFICATION = b'\x11'
    BURN_INPUT_HASHES = b'\x13'

    TRANSACTION_BATCH = b'\x15'



    

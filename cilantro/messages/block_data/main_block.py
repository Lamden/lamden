from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property
from typing import List

import capnp
import blockdata_capnp

class MainBlock(MessageBase):
    """
    This class acts a structure that holds all information necessary to validate and build a block. In particular, this
    means the information carried in this class provide everything an actor needs to insert a new entry into the
    'blocks' table (see schema specified in storage/blocks.py). It DOES NOT contain the actual transactions associated with
    a block, but rather the Merkle leaves of the block (ie hashes of the block's transactions). After a delegate
    parses this class, it must request a TransactionRequest to get the actual raw transaction data.
    """
    pass

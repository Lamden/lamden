import asyncio

from cilantro_ee.crypto.merkle_tree import merklize
from cilantro_ee.crypto.wallet import _verify
from cilantro_ee.logger.base import get_logger
from cilantro_ee.messages import Message, MessageType
from cilantro_ee.sockets.inbox import SecureAsyncInbox
from cilantro_ee.storage import BlockchainDriver


class SBCInbox(SecureAsyncInbox):
    def __init__(self, driver: BlockchainDriver, expected_subblocks=4, debug=True, *args, **kwargs):
        self.q = []
        self.driver = driver
        self.expected_subblocks = expected_subblocks
        self.log = get_logger('SBC')
        self.log.propagate = debug
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

        self.log.info(f'Got message on SBCInbox')

        # Ignore bad message types
        if msg_type != MessageType.SUBBLOCK_CONTENDERS:
            self.log.error('Wrong SBC message type. Tossing.')
            return

        if len(msg_blob.contenders) != self.expected_subblocks:
            self.log.error('Contender does not have enough subblocks. Tossing.')
            return

        # Make sure all the contenders are valid
        all_valid = True
        for i in range(len(msg_blob.contenders)):
            try:
                self.sbc_is_valid(msg_blob.contenders[i], i)
            except SBCException as e:
                self.log.error(type(e))
                all_valid = False

        # Add the whole contender
        if all_valid:
            self.q.append(msg_blob.contenders)
            self.log.info('Added new SBC')

    def sbc_is_valid(self, sbc, sb_idx=0):
        if sbc.subBlockNum != sb_idx:
            raise SBCIndexMismatchError

        # Make sure signer is in the delegates
        if len(sbc.transactions) == 0:
            msg = bytes.fromhex(sbc.inputHash)
        else:
            msg = sbc.merkleTree.leaves[0]

        valid_sig = _verify(
            vk=sbc.signer,
            msg=msg,
            signature=sbc.merkleTree.signature
        )

        if not valid_sig:
            raise SBCInvalidSignatureError

        # if sbc.prevBlockHash != self.driver.latest_block_hash:
        #     self.log.info(sbc.prevBlockHash)
        #     self.log.info(self.driver.latest_block_hash)
        #     raise SBCBlockHashMismatchError

        # idk
        if len(sbc.merkleTree.leaves) > 0:
            txs = [tx.as_builder().to_bytes_packed() for tx in sbc.transactions]
            expected_tree = merklize(txs)

            for i in range(len(expected_tree)):
                if expected_tree[i] != sbc.merkleTree.leaves[i]:
                    raise SBCMerkleLeafVerificationError

    def has_sbc(self):
        return len(self.q) > 0

    async def receive_sbc(self):
        self.log.info('Waiting for an SBC...')
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        self.log.info('Got one! Returning...')
        return self.q.pop(0)


class SBCException(Exception):
    pass


class SBCBadMessage(SBCException):
    pass


class SBCInvalidSignatureError(SBCException):
    pass


class SBCBlockHashMismatchError(SBCException):
    pass


class SBCMerkleLeafVerificationError(SBCException):
    pass


class SBCIndexMismatchError(SBCException):
    pass


class SBCIndexGreaterThanPossibleError(SBCException):
    pass
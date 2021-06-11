from contracting.db.encoder import encode
from lamden.crypto.wallet import verify
from lamden.logger.base import get_logger

import hashlib

class Block_Contender():
    def __init__(self, validation_queue, get_all_peers, check_peer_in_consensus,
                 peer_add_strike, wallet, debug=True):
        self.q = []
        self.expected_subblocks = 1
        self.log = get_logger('Block Contender')
        self.log.propagate = debug
        self.wallet = wallet

        self.block_q = []
        self.validation_queue = validation_queue
        self.get_all_peers = get_all_peers
        self.check_peer_in_consensus = check_peer_in_consensus
        self.peer_add_strike = peer_add_strike

    async def process_message(self, msg):
        # self.log.debug(msg)
        # self.log.debug(f'message length: {len(msg)}')
        # Ignore bad message types
        # Ignore if not enough subblocks
        # Make sure all the contenders are valid

        peers = self.get_all_peers()

        subblock = msg['subblocks'][0]
        message = subblock['transactions'][0]
        signing_data = subblock['signatures'][0]
        # self.log.info(f'Received BLOCK {msg["hash"][:8]} from {signing_data["signer"][:8]}')

        if signing_data['signer'] not in peers and signing_data['signer'] != self.wallet.verifying_key:
            # TODO not sure how we would have connections from peers that are't in the quorum but we should blacklist these connection
            self.log.error('Contender sender is not a valid peer!')
            return

        if not self.check_peer_in_consensus(signing_data['signer']):
            # TODO implement some logic to disconnect(blacklist) from the peer if they send consecutive bad solutions upto X number of times
            # TODO ie, it's upto the peer to know they are out of consensus and attempt to resync and rejoin or be at risk of being blacklisted
            self.log.info(f'{signing_data["signer"][:8]} is not in the consensus group. Ignoring solution!')
            return

        if not self.bc_is_valid(
            message=message,
            signer=signing_data['signer'],
            signature=signing_data['signature']
        ):
            self.log.error('Contender is not valid!')
            return

        # Get the transaction
        tx = subblock['transactions'][0]

        # Add solution to this validation list for this tx
        self.validation_queue.add_solution(
            hlc_timestamp=tx['hlc_timestamp'],
            node_vk=signing_data['signer'],
            block_info = msg
        )

    def bc_is_valid(self, message, signer, signature):
        h = hashlib.sha3_256()
        h.update('{}'.format(encode(message).encode()).encode())
        message_hash = h.hexdigest()

        valid_sig = verify(
            vk=signer,
            msg=message_hash,
            signature=signature
        )

        if not valid_sig:
            self.log.debug({
                'vk': signer,
                'msg': message,
                'signature': signature
            })
            self.log.error(f'Solution from {signer[:8]} has an invalid signature.')
            return False

        return True
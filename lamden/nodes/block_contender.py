from contracting.db.encoder import encode
from lamden.crypto.wallet import verify
from lamden.logger.base import get_logger

import hashlib

class Block_Contender():
    def __init__(self, validation_queue, get_all_peers, check_peer_in_consensus, get_last_hlc_in_consensus,
                 peer_add_strike, wallet, debug=False, testing=False):
        self.q = []
        self.expected_subblocks = 1
        self.log = get_logger('Block Contender')
        self.log.propagate = debug
        self.wallet = wallet

        self.block_q = []
        self.validation_queue = validation_queue
        self.get_all_peers = get_all_peers
        self.check_peer_in_consensus = check_peer_in_consensus
        self.get_last_hlc_in_consensus = get_last_hlc_in_consensus
        self.peer_add_strike = peer_add_strike

        self.debug = debug
        self.testing = testing
        self.debug_recieved_solutions = []

    async def process_message(self, msg):
        # self.log.debug(msg)
        # self.log.debug(f'message length: {len(msg)}')
        # Ignore bad message types
        # Ignore if not enough subblocks
        # Make sure all the contenders are valid

        # get the tx specifics, if there is an error here then the tx is malformed
        try:
            subblock = msg['subblocks'][0]
            signing_data = subblock['signatures'][0]
            signer = signing_data['signer']
            tx = subblock['transactions'][0]
            hlc_timestamp = tx['hlc_timestamp']
        except Exception:
            self.log.error("Malformed solution from peer.")

        self.debug_recieved_solutions.append({hlc_timestamp: [signing_data['signer'], msg['hash']]})

        # ignore this solution if we have already determined consensus on a previous HLC
        if hlc_timestamp <= self.get_last_hlc_in_consensus(): return

        peers = self.get_all_peers()
        # self.log.info(f'Received BLOCK {msg["hash"][:8]} from {signer[:8]}')

        if signer not in peers and signer != self.wallet.verifying_key:
            # TODO not sure how we would have connections from peers that are't in the quorum but we should blacklist these connection
            self.log.error('Contender sender is not a valid peer!')
            return

        if not self.check_peer_in_consensus(signer):
            # TODO implement some logic to disconnect(blacklist) from the peer if they send consecutive bad solutions upto X number of times
            # TODO ie, it's upto the peer to know they are out of consensus and attempt to resync and rejoin or be at risk of being blacklisted
            self.log.info(f'{signer[:8]} is not in the consensus group. Ignoring solution!')
            return

        if not self.bc_is_valid(
            message=tx,
            signer=signer,
            signature=signing_data['signature']
        ):
            self.log.error('Contender is not valid!')
            return

        # TODO Check to see if this is for a block already in consensus
        # Add solution to this validation list for this tx
        self.validation_queue.append(
            hlc_timestamp=tx['hlc_timestamp'],
            node_vk=signer,
            block_info=msg
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
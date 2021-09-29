from contracting.db.encoder import encode
from lamden.crypto.wallet import verify
from lamden.logger.base import get_logger
from lamden.crypto.canonical import tx_hash_from_tx

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

        if not self.valid_message_payload(msg=msg):
            self.log.error(
                f'Received Invalid Processing Results from {msg.get("proof", "No Proof provided")}'
            )
            return

        # get the tx specifics, if there is an error here then the tx is malformed

        tx_result = msg['tx_result']
        proof = msg["proof"]
        hlc_timestamp = msg['hlc_timestamp']

        self.debug_recieved_solutions.append({hlc_timestamp: [proof['signer'], proof['tx_result_hash']]})

        if not self.validate_message_signature(tx_result=tx_result, proof=proof, hlc_timestamp=hlc_timestamp):
            self.log.debug(f"Could not verify message signature {msg['proof']}")
            return

        peers = self.get_all_peers()
        # self.log.info(f'Received BLOCK {msg["hash"][:8]} from {signer[:8]}')

        if proof['signer'] not in peers and proof['signer'] != self.wallet.verifying_key:
            # TODO not sure how we would have connections from peers that are't in the quorum but we should blacklist these connection
            self.log.error('Contender sender is not a valid peer!')
            return

        if not self.check_peer_in_consensus(proof['signer']):
            # TODO implement some logic to disconnect(blacklist) from the peer if they send consecutive bad solutions upto X number of times
            # TODO ie, it's upto the peer to know they are out of consensus and attempt to resync and rejoin or be at risk of being blacklisted
            self.log.info(f"{proof['signer'][:8]} is not in the consensus group. Ignoring solution!")
            return

        # TODO Check to see if this is for a block already in consensus

        # Add solution to this validation list for this tx
        self.validation_queue.append(processing_results=msg)

    def validate_message_signature(self, tx_result, proof, hlc_timestamp):
        # Sign our tx results
        h = hashlib.sha3_256()
        h.update('{}'.format(encode(tx_result).encode()).encode())
        h.update('{}'.format(hlc_timestamp).encode())
        tx_result_hash = h.hexdigest()

        valid_sig = verify(
            vk=proof['signer'],
            msg=tx_result_hash,
            signature=proof['signature']
        )

        if not valid_sig:
            self.log.debug(proof)
            self.log.error(f"Solution from {proof['signer'][:8]} has an invalid signature.")
            return False

        return True

    def valid_message_payload(self, msg):
        if msg.get("tx_result", None) is None:
            return False
        if msg["tx_result"].get("transaction", None) is None:
            return False
        if msg.get("hlc_timestamp", None) is None:
            return False
        if msg.get("proof", None) is None:
            return False
        if msg["proof"].get("signature", None) is None:
            return False
        if msg["proof"].get("signer", None) is None:
            return False
        if msg["proof"].get("tx_result_hash", None) is None:
            return False
        return True
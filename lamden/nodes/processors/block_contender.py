from lamden.crypto.wallet import verify
from lamden.logger.base import get_logger
from lamden.crypto.canonical import tx_result_hash_from_tx_result_object
from lamden.network import Network

class Block_Contender():
    def __init__(self, validation_queue, get_block_by_hlc, wallet, network: Network, debug=False, testing=False):

        self.q = []
        self.expected_subblocks = 1
        self.log = get_logger('Block Contender')
        self.log.propagate = debug
        self.wallet = wallet

        self.block_q = []
        self.validation_queue = validation_queue
        self.get_block_by_hlc = get_block_by_hlc

        self.network = network

        self.debug = debug
        self.testing = testing
        self.debug_recieved_solutions = []

    async def process_message(self, msg):

        # Make sure the message has the correct properties to process
        if not self.valid_message_payload(msg=msg):
            self.log.error(
                f'Received Invalid Processing Results from {msg.get("proof", "No Proof provided")}'
            )
            self.log.error(msg)
            return

        tx_result = msg['tx_result']
        proof = msg["proof"]
        hlc_timestamp = msg['hlc_timestamp']

        # Create a hash of the tx_result
        tx_result_hash = tx_result_hash_from_tx_result_object(tx_result=tx_result, hlc_timestamp=hlc_timestamp)
        #self.debug_recieved_solutions.append({hlc_timestamp: [proof['signer'], tx_result_hash]})

        if not self.validate_message_signature(tx_result_hash=tx_result_hash, proof=proof):
            self.log.debug(f"Could not verify message signature {msg['proof']}")
            return

        # tack on the tx_result_hash to the proof for this node
        msg['proof']['tx_result_hash'] = tx_result_hash

        peers = self.network.get_all_peers()
        # self.log.info(f'Received BLOCK {msg["hash"][:8]} from {signer[:8]}')

        if proof['signer'] not in peers and proof['signer'] != self.wallet.verifying_key:
            # TODO not sure how we would have connections from peers that are't in the quorum but we should blacklist these connection
            self.log.error('Contender sender is not a valid peer!')
            return

        '''
        if not self.network.check_peer_in_consensus(proof['signer']):
            # TODO implement some logic to disconnect(blacklist) from the peer if they send consecutive bad solutions upto X number of times
            # TODO ie, it's upto the peer to know they are out of consensus and attempt to resync and rejoin or be at risk of being blacklisted
            self.log.info(f"{proof['signer'][:8]} is not in the consensus group. Ignoring solution!")
            return
        '''

        if hlc_timestamp < self.validation_queue.last_hlc_in_consensus:
            block = self.get_block_by_hlc(hlc_timestamp=hlc_timestamp)
            if block is not None:
                return

        # TODO Check to see if this is for a block already in consensus

        # Add solution to this validation list for this tx
        self.validation_queue.append(processing_results=msg)

    def validate_message_signature(self, tx_result_hash, proof):
        try:
            return verify(vk=proof['signer'], msg=tx_result_hash, signature=proof['signature'])
        except Exception:
            return False

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

        return True

from contracting.db.encoder import encode
from collections import defaultdict
from lamden import router
from lamden.crypto.canonical import merklize, block_from_subblocks
from lamden.crypto.wallet import verify
from lamden.logger.base import get_logger
from lamden import storage
import asyncio
import time
import hashlib

log = get_logger('Contender')

class SBCInbox(router.Processor):
    def __init__(self, validation_queue, get_all_peers, check_peer_in_consensus, wallet, debug=True):
        self.q = []
        self.expected_subblocks = 1
        self.log = get_logger('Subblock Gatherer')
        self.log.propagate = debug
        self.wallet = wallet

        self.block_q = []
        self.validation_queue = validation_queue
        self.get_all_peers = get_all_peers
        self.check_peer_in_consensus = check_peer_in_consensus

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
            self.log.error('Contender sender is not a valid peer!')
            return

        if not self.check_peer_in_consensus(signing_data['signer']):
            # TODO implement some logic to disconnect(blacklist) from the peer if they send consecutive bad solutions upto X number of times
            # TODO ie, it's upto the peer to know they are out of consensus and attempt to resync and rejoin, if not we stop communicating with them
            self.log.info(f'{signing_data["signer"][:8]} is not in the consensus group. Ignoring solution!')
            return

        if not self.sbc_is_valid(
            message=message,
            signer=signing_data['signer'],
            signature=signing_data['signature']
        ):
            self.log.error('Contender is not valid!')
            return

        # Get the transaction
        tx = subblock['transactions'][0]

        # self.log.info(msg[i]['signer'])
        if self.validation_queue.is_duplicate(hlc_timestamp=tx['hlc_timestamp'], node_vk=signing_data['signer']):
            # TODO what todo if you get a duplicate result from the same node?  Possible fraud detection?
            self.log.error(f'Already received results from {signing_data["signer"]} for {tx["hlc_timestamp"]}')
            return

        # Add solution to this validation list for this tx
        self.validation_queue.add_solution(
            hlc_timestamp=tx['hlc_timestamp'],
            node_vk=signing_data['signer'],
            block_info = msg
        )

    def sbc_is_valid(self, message, signer, signature):
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

    def has_sbc(self):
        return len(self.q) > 0

    async def receive_sbc(self):
        self.log.debug('Receiving Subblock Contender...')
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        return self.q.pop(0)


class PotentialSolution:
    def __init__(self, struct):
        self.struct = struct
        self.signatures = []

    @property
    def votes(self):
        return len(self.signatures)

    def struct_to_dict(self):
        subblock = {
            'input_hash': self.struct['input_hash'],
            'transactions': self.struct['transactions'],
            'merkle_leaves': self.struct['merkle_tree']['leaves'],
            'subblock': self.struct['subblock'],
            'signatures': []
        }

        for sig in self.signatures:
            subblock['signatures'].append({
                'signature': sig[0],
                'signer': sig[1]
            })

        subblock['signatures'].sort(key=lambda i: i['signer'])

        return subblock


class SubBlockContender:
    def __init__(self, input_hash, index, total_contacts, required_consensus=0.66, adequate_consensus=0.51):
        self.input_hash = input_hash
        self.index = index

        self.potential_solutions = {}
        self.best_solution = None

        self.total_responses = 0
        self.total_contacts = total_contacts

        self.required_consensus = required_consensus
        self.adequate_consensus = adequate_consensus

        self.log = get_logger('SBC')

    def add_potential_solution(self, sbc):
        result_hash = sbc['merkle_tree']['leaves'][0]

        # Create a new potential solution if it is a new result hash
        if self.potential_solutions.get(result_hash) is None:
            self.potential_solutions[result_hash] = PotentialSolution(struct=sbc)
            # self.log.info(f'New result found. Creating a new solution: {result_hash[:8]}')

        # Add the signature to the potential solution
        p = self.potential_solutions.get(result_hash)
        p.signatures.append((sbc['merkle_tree']['signature'], sbc['signer']))

        # Update the best solution if the current potential solution now has more votes
        if self.best_solution is None or p.votes > self.best_solution.votes:
            self.best_solution = p
            # self.log.info(f'New best result: {result_hash[:8]}')

        # self.log.info(f'Best solution votes: {self.best_solution.votes}')

        self.total_responses += 1

    @property
    def failed(self):
        # True if all responses are recorded and required consensus is not possible
        if self.total_responses >= self.total_contacts and \
               not self.has_required_consensus:
            log.error('Failed block created!')
            return True
        return False

    @property
    def has_required_consensus(self):
        if self.best_solution is None:
            return False

        if self.best_solution.votes / self.total_contacts < self.required_consensus:
            return False

        return True

    @property
    def has_adequate_consensus(self):
        if self.best_solution is None:
            return False

        if self.best_solution.votes / self.total_contacts < self.adequate_consensus:
            return False

        return True

    @property
    def serialized_solution(self):
        #if not self.has_adequate_consensus or self.failed:
        #    return None

        try:
            return self.best_solution.struct_to_dict()
        except:
            return None


class BlockContender:
    def __init__(self, total_contacts, total_subblocks, required_consensus=0.66, acceptable_consensus=0.5):
        self.total_contacts = total_contacts
        self.total_subblocks = total_subblocks

        self.required_consensus = required_consensus

        # Acceptable consensus forces a block to complete. Anything below this will fail.
        self.acceptable_consensus = acceptable_consensus

        # Create an empty list to store the contenders as they come in
        self.subblock_contenders = [None for _ in range(self.total_subblocks)]

        self.log = get_logger('Aggregator')

        self.received = defaultdict(set)

    def add_sbcs(self, sbcs):
        for sbc in sbcs:
            # If it's out of range, ignore
            if sbc['subblock'] > self.total_subblocks - 1:
                continue

            if sbc['signer'] in self.received[sbc['subblock']]:
                continue

            # If it's the first contender, create a new object and store it
            if self.subblock_contenders[sbc['subblock']] is None:
                #self.log.info('First block. Making a new solution object.')
                s = SubBlockContender(
                    input_hash=sbc['input_hash'],
                    index=sbc['subblock'],
                    total_contacts=self.total_contacts
                )
                self.subblock_contenders[sbc['subblock']] = s

            # Access the object at the SB index and add a potential solution
            s = self.subblock_contenders[sbc['subblock']]
            s.add_potential_solution(sbc)
            self.received[sbc['subblock']].add(sbc['signer'])

    def current_responded_sbcs(self):
        i = 0
        for s in self.subblock_contenders:
            if s is not None:
                i += 1

        return i

    def block_has_consensus(self):
        for sb in self.subblock_contenders:
            if sb is None:
                return False
            if not sb.has_required_consensus:
                return False

        return True

    def get_current_best_block(self):
        block = []

        # Where None is appended = failed
        for sb in self.subblock_contenders:
            if sb is None:
                block.append(None)
            else:
                block.append(sb.serialized_solution)

        return block

    @property
    def responses(self):
        m = 0
        for sb in self.subblock_contenders:
            if sb is None:
                continue
            if sb.total_responses > m:
                m = sb.total_responses

        return m


# Can probably move this into the masternode. Move the sbc inbox there and deprecate this class
class Aggregator:
    def __init__(self, validation_queue, get_all_peers, driver, wallet, expected_subblocks=4, seconds_to_timeout=6, debug=True):
        self.expected_subblocks = expected_subblocks
        self.sbc_inbox = SBCInbox(
            validation_queue=validation_queue,
            get_all_peers=get_all_peers,
            wallet=wallet
        )

        self.driver = driver

        self.seconds_to_timeout = seconds_to_timeout

        self.log = get_logger('AGG')
        self.log.propagate = debug

    async def gather_subblocks(self, total_contacts, current_height=0, current_hash='0' * 64, quorum_ratio=0.66, adequate_ratio=0.5, expected_subblocks=4):
        self.sbc_inbox.expected_subblocks = expected_subblocks

        block = storage.get_latest_block_height(self.driver)

        self.log.info(f'Expecting {expected_subblocks} subblocks from {total_contacts} delegates.')

        contenders = BlockContender(
            total_contacts=total_contacts,
            required_consensus=quorum_ratio,
            total_subblocks=expected_subblocks,
            acceptable_consensus=adequate_ratio
        )

        # Add timeout condition.
        started = time.time()
        last_log = started
        while (not contenders.block_has_consensus() and contenders.responses < contenders.total_contacts) and \
                time.time() - started < self.seconds_to_timeout:

            if self.sbc_inbox.has_sbc():
                sbcs = await self.sbc_inbox.receive_sbc() # Can probably make this raw sync code
                self.log.info('Pop it in there.')
                contenders.add_sbcs(sbcs)

            if time.time() - last_log > 5:
                self.log.error(f'Waiting for contenders for {int(time.time() - started)}s.')
                last_log = time.time()

            await asyncio.sleep(0)

        if time.time() - started > self.seconds_to_timeout:
            self.log.error(f'Block timeout. Too many delegates are offline! Kick out the non-responsive ones! {block}')

        self.log.info('Done aggregating new block.')

        block = contenders.get_current_best_block()
        self.sbc_inbox.q.clear()

        # self.log.info(f'Best block: {block}')

        return block_from_subblocks(
            block,
            previous_hash=current_hash,
            block_num=current_height + 1
        )
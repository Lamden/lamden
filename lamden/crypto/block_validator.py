from iso8601 import parse_date
from lamden.crypto.canonical import create_proof_message_from_proof, block_hash_from_block, tx_hash_from_tx, format_dictionary, tx_result_hash_from_tx_result_object, hash_genesis_block_state_changes
from contracting.db.encoder import encode
from lamden.logger.base import get_logger
from lamden.crypto.wallet import verify
from lamden.utils import hlc
from copy import deepcopy

GENESIS_BLOCK_NUMBER = "0"
GENESIS_HLC_TIMESTAMP = '0000-00-00T00:00:00.000000000Z_0'
GENESIS_PREVIOUS_HASH = '0' * 64
GENESIS_BLOCK_NUMBER_OF_KEYS = 6

BLOCK_NUMBER_OF_KEYS = 9

EXCEPTION_BLOCK_HASH_MALFORMED = "Block Hash is Malformed."
EXCEPTION_BLOCK_PREVIOUS_HASH_MALFORMED = "Block Previous Hash is Malformed."
EXCEPTION_BLOCK_NUMBER_INVALID = "Block Number is Invalid."
EXCEPTION_BLOCK_HLC_INVALID = "Block HLC Timestamp is Invalid."
EXCEPTION_BLOCK_ORIGIN_INVALID = "Block Origin is Invalid."
EXCEPTION_BLOCK_ORIGIN_SENDER_MALFORMED = "Block Origin Sender is Malformed."
EXCEPTION_BLOCK_ORIGIN_SIGNATURE_MALFORMED = "Block Origin Signature is Malformed."
EXCEPTION_BLOCK_REWARDS_INVALID = "Block Rewards are Invalid."
EXCEPTION_BLOCK_PROOFS_INVALID = "Block Proofs are Invalid."
EXCEPTION_BLOCK_PROOF_MALFORMED = "Block Proof is Malformed."
EXCEPTION_BLOCK_PROOFS_INVALID_CONSENSUS = "Invalid Number of Block Proofs for Consensus."
EXCEPTION_BLOCK_MINTER_SIGNATURE_MALFORMED = "Block Minter Signature is Malformed."
EXCEPTION_BLOCK_MINTED_INVALID = "Block Minted is Invalid."
EXCEPTION_BLOCK_PROCESSED_INVALID = "Block Processed is Invalid."
EXCEPTION_BLOCK_KEYS_INVALID_NUMBER = f"Block should only have {BLOCK_NUMBER_OF_KEYS} keys."

EXCEPTION_GENESIS_BLOCK_HLC_INVALID = f"Genesis Block HLC is Invalid. Should be '{GENESIS_HLC_TIMESTAMP}'."
EXCEPTION_GENESIS_BLOCK_NUMBER_INVALID = f"Genesis Block Number is Invalid. Should be {GENESIS_BLOCK_NUMBER}."
EXCEPTION_GENESIS_BLOCK_PREVIOUS_HASH_INVALID = f"Genesis Block Previous Hash is Invalid. Should be {GENESIS_PREVIOUS_HASH}."
EXCEPTION_GENESIS_BLOCK_KEYS_INVALID_NUMBER = f"Genesis Block should only have {GENESIS_BLOCK_NUMBER_OF_KEYS} keys."

BLOCK_EXCEPTIONS = {
    'BlockHashMalformed': EXCEPTION_BLOCK_HASH_MALFORMED,
    'BlockPreviousHashMalformed': EXCEPTION_BLOCK_PREVIOUS_HASH_MALFORMED,
    'BlockNumberInvalid': EXCEPTION_BLOCK_NUMBER_INVALID,
    'BlockHLCInvalid': EXCEPTION_BLOCK_HLC_INVALID,
    'BlockOriginInvalid': EXCEPTION_BLOCK_ORIGIN_INVALID,
    'BlockOriginSenderMalformed': EXCEPTION_BLOCK_ORIGIN_SENDER_MALFORMED,
    'BlockOriginSignatureMalformed': EXCEPTION_BLOCK_ORIGIN_SIGNATURE_MALFORMED,
    'BlockRewardsInvalid': EXCEPTION_BLOCK_REWARDS_INVALID,
    'BlockProofsInvalid': EXCEPTION_BLOCK_PROOFS_INVALID,
    'BlockProofMalformed': EXCEPTION_BLOCK_PROOF_MALFORMED,
    'BlockProofsInvalidConsensus': EXCEPTION_BLOCK_PROOFS_INVALID_CONSENSUS,
    'BlockProcessedInvalid': EXCEPTION_BLOCK_PROCESSED_INVALID,
    'BlockKeysInvalidNumber': EXCEPTION_BLOCK_KEYS_INVALID_NUMBER,
    'GenesisBlockNumberInvalid': EXCEPTION_GENESIS_BLOCK_NUMBER_INVALID,
    'GenesisBlockHLCInvalid': EXCEPTION_GENESIS_BLOCK_HLC_INVALID,
    'GenesisBlockPreviousHashInvalid': EXCEPTION_GENESIS_BLOCK_PREVIOUS_HASH_INVALID,
    'GenesisBlockKeysInvalidNumber': EXCEPTION_GENESIS_BLOCK_KEYS_INVALID_NUMBER
}

class BlockHashMalformed(Exception):
    pass

class BlockPreviousHashMalformed(Exception):
    pass

class BlockNumberInvalid(Exception):
    pass

class BlockHLCInvalid(Exception):
    pass

class BlockOriginInvalid(Exception):
    pass

class BlockOriginSenderMalformed(Exception):
    pass

class BlockOriginSignatureMalformed(Exception):
    pass

class BlockRewardsInvalid(Exception):
    pass

class BlockProofsInvalid(Exception):
    pass

class BlockProofMalformed(Exception):
    pass

class BlockProofsInvalidConsensus(Exception):
    pass

class BlockMinterSignatureMalformed(Exception):
    pass

class BlockMintedInvalid(Exception):
    pass

class BlockProcessedInvalid(Exception):
    pass

class BlockKeysInvalidNumber(Exception):
    pass

class GenesisBlockNumberInvalid(Exception):
    pass

class GenesisBlockHLCInvalid(Exception):
    pass

class GenesisBlockPreviousHashInvalid(Exception):
    pass

class GenesisBlockKeysInvalidNumber(Exception):
    pass


def validate_block_structure(block: dict) -> bool:
    if not isinstance(block, dict):
        return False

    number = block.get('number')
    if not isinstance(number, str):
        raise BlockNumberInvalid(EXCEPTION_BLOCK_NUMBER_INVALID)

    hash_str = block.get('hash')
    if not hash_is_sha256(hash_str=hash_str):
        raise BlockHashMalformed(EXCEPTION_BLOCK_HASH_MALFORMED)

    previous_hash_str = block.get('previous')
    if not hash_is_sha256(hash_str=previous_hash_str):
        raise BlockPreviousHashMalformed(EXCEPTION_BLOCK_PREVIOUS_HASH_MALFORMED)

    origin = block.get('origin')
    if not isinstance(origin, dict):
        raise BlockOriginInvalid(EXCEPTION_BLOCK_ORIGIN_INVALID)

    origin_sender = origin.get('sender')
    if not hash_is_sha256(origin_sender):
        raise BlockOriginSenderMalformed(EXCEPTION_BLOCK_ORIGIN_SENDER_MALFORMED)

    origin_signature = origin.get('signature')
    if not hash_is_sha256_signature(origin_signature):
        raise BlockOriginSignatureMalformed(EXCEPTION_BLOCK_ORIGIN_SIGNATURE_MALFORMED)

    genesis = block.get('genesis')
    if not isinstance(genesis, list):
        hlc_timestamp = block.get('hlc_timestamp')
        if not is_iso8601_hlc_timestamp(hlc_timestamp=hlc_timestamp):
            raise BlockHLCInvalid(EXCEPTION_BLOCK_HLC_INVALID)

        expected_number = str(hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp))
        if expected_number != number:
            raise BlockNumberInvalid(EXCEPTION_BLOCK_NUMBER_INVALID)

        rewards = block.get('rewards')
        if not isinstance(rewards, list):
            raise BlockRewardsInvalid(EXCEPTION_BLOCK_REWARDS_INVALID)

        proofs = block.get('proofs')
        if not isinstance(proofs, list) or len(proofs) < 1:
            raise BlockProofsInvalid(EXCEPTION_BLOCK_PROOFS_INVALID)

        processed_transaction = block.get('processed')
        if not isinstance(processed_transaction, dict):
            raise BlockProcessedInvalid(EXCEPTION_BLOCK_PROCESSED_INVALID)

        minted = block.get('minted')
        if not isinstance(minted, dict) or len(minted.keys()) != 2 or not minted.get('minter') or not minted.get('signature'):
            raise BlockMintedInvalid(EXCEPTION_BLOCK_MINTED_INVALID)

        if len(block.keys()) != BLOCK_NUMBER_OF_KEYS:
            raise BlockKeysInvalidNumber(EXCEPTION_BLOCK_KEYS_INVALID_NUMBER)

        validate_processed_transaction_structure(processed_transaction=processed_transaction)
    else:
        hlc_timestamp = block.get('hlc_timestamp')
        if hlc_timestamp != GENESIS_HLC_TIMESTAMP:
            raise GenesisBlockHLCInvalid(EXCEPTION_GENESIS_BLOCK_HLC_INVALID)

        number = block.get('number')
        if number != GENESIS_BLOCK_NUMBER:
            raise GenesisBlockNumberInvalid(EXCEPTION_GENESIS_BLOCK_NUMBER_INVALID)

        previous_hash_str = block.get('previous')
        if previous_hash_str != GENESIS_PREVIOUS_HASH:
            raise GenesisBlockPreviousHashInvalid(EXCEPTION_GENESIS_BLOCK_PREVIOUS_HASH_INVALID)

        if len(block.keys()) != GENESIS_BLOCK_NUMBER_OF_KEYS:
            raise GenesisBlockKeysInvalidNumber(EXCEPTION_GENESIS_BLOCK_KEYS_INVALID_NUMBER)

    return True


EXCEPTION_PROCESSED_TX_HASH_MALFORMED = "Processed Transaction Hash is Malformed."
EXCEPTION_PROCESSED_TX_RESULT_INVALID = "Processed Transaction Result is Invalid."
EXCEPTION_PROCESSED_STAMPS_USED_INVALID = "Processed Transaction Stamps Used is Invalid."
EXCEPTION_PROCESSED_STATE_INVALID = "Processed Transaction State Invalid."
EXCEPTION_PROCESSED_STATE_ENTRY_INVALID = "Processed Transaction State Entry Invalid."
EXCEPTION_PROCESSED_STATUS_INVALID = "Process Transaction Status is Invalid."
EXCEPTION_PROCESSED_TRANSACTION_PAYLOAD_INVALID = "Process Transaction Payload is Invalid."

PROCESSED_TX_EXCEPTIONS = {
    'ProcessedTxHashMalformed': EXCEPTION_PROCESSED_TX_HASH_MALFORMED,
    'ProcessedTxResultInvalid': EXCEPTION_PROCESSED_TX_RESULT_INVALID,
    'ProcessedTxStampsUsedInvalid': EXCEPTION_PROCESSED_STAMPS_USED_INVALID,
    'ProcessedTxStateInvalid': EXCEPTION_PROCESSED_STATE_INVALID,
    'ProcessedTxStateEntryInvalid': EXCEPTION_PROCESSED_STATE_ENTRY_INVALID,
    'ProcessedTxStatusInvalid': EXCEPTION_PROCESSED_STATUS_INVALID,
    'ProcessedTransactionPayloadInvalid': EXCEPTION_PROCESSED_TRANSACTION_PAYLOAD_INVALID
}

class ProcessedTxHashMalformed(Exception):
    pass

class ProcessedTxResultInvalid(Exception):
    pass

class ProcessedTxStampsUsedInvalid(Exception):
    pass

class ProcessedTxStateInvalid(Exception):
    pass

class ProcessedTxStateEntryInvalid(Exception):
    pass

class ProcessedTxStatusInvalid(Exception):
    pass

class ProcessedTransactionPayloadInvalid(Exception):
    pass

def validate_processed_transaction_structure(processed_transaction: dict) -> bool:
    if not isinstance(processed_transaction, dict):
        return False

    hash_str = processed_transaction.get('hash')
    if not hash_is_sha256(hash_str=hash_str):
        raise ProcessedTxHashMalformed(EXCEPTION_PROCESSED_TX_HASH_MALFORMED)

    if 'result' not in processed_transaction:
        raise ProcessedTxResultInvalid(EXCEPTION_PROCESSED_TX_RESULT_INVALID)

    result = processed_transaction.get('result')
    if not isinstance(result, str):
        raise ProcessedTxResultInvalid(EXCEPTION_PROCESSED_TX_RESULT_INVALID)

    stamps_used = processed_transaction.get('stamps_used')
    if not isinstance(stamps_used, int) or stamps_used < 0:
        raise ProcessedTxStampsUsedInvalid(EXCEPTION_PROCESSED_STAMPS_USED_INVALID)

    state = processed_transaction.get('state')
    if not isinstance(state, list):
        raise ProcessedTxStateInvalid(EXCEPTION_PROCESSED_STATE_INVALID)

    for state_entry in state:
        if (not isinstance(state_entry, dict) or
           not ('key' in state_entry and 'value' in state_entry) or
           not isinstance(state_entry['key'], str)):
            raise ProcessedTxStateEntryInvalid(EXCEPTION_PROCESSED_STATE_ENTRY_INVALID)

    status = processed_transaction.get('status')
    if not isinstance(status, int):
        raise ProcessedTxStatusInvalid(EXCEPTION_PROCESSED_STATUS_INVALID)

    transaction = processed_transaction.get('transaction')
    if not isinstance(transaction, dict):
        raise ProcessedTransactionPayloadInvalid(EXCEPTION_PROCESSED_TRANSACTION_PAYLOAD_INVALID)

    validate_transaction_structure(transaction=transaction)

    return True

EXCEPTION_TRANSACTION_METADATA_INVALID = "Transaction Metadata is Invalid."
EXCEPTION_TRANSACTION_METADATA_SIGNATURE_MALFORMED = "Transaction Metadata Signature is Malformed."
EXCEPTION_TRANSACTION_PAYLOAD_INVALID = "Transaction Payload is Invalid."
EXCEPTION_TRANSACTION_PAYLOAD_CONTRACT_INVALID = "Transaction Payload Contract is Invalid."
EXCEPTION_TRANSACTION_PAYLOAD_FUNCTION_INVALID = "Transaction Payload Function is Invalid."
EXCEPTION_TRANSACTION_PAYLOAD_KWARGS_INVALID = "Transaction Payload KWARGS are Invalid."
EXCEPTION_TRANSACTION_PAYLOAD_NONCE_INVALID = "Transaction Payload Nonce is Invalid."
EXCEPTION_TRANSACTION_PROCESSOR_MALFORMED = "Transaction Payload Processor is Malformed."
EXCEPTION_TRANSACTION_SENDER_MALFORMED = "Transaction Payload Sender is Malformed."
EXCEPTION_TRANSACTION_PAYLOAD_STAMPS_SUPPLIED_INVALID = "Transaction Payload Stamps Supplied is Invalid."


PAYLOAD_EXCEPTIONS = {
    'TransactionMetadataInvalid': EXCEPTION_TRANSACTION_METADATA_INVALID,
    'TransactionMetadataSignatureMalformed': EXCEPTION_TRANSACTION_METADATA_SIGNATURE_MALFORMED,
    'TransactionPayloadInvalid': EXCEPTION_TRANSACTION_PAYLOAD_INVALID,
    'TransactionPayloadContractInvalid': EXCEPTION_TRANSACTION_PAYLOAD_CONTRACT_INVALID,
    'TransactionPayloadFunctionInvalid': EXCEPTION_TRANSACTION_PAYLOAD_FUNCTION_INVALID,
    'TransactionPayloadKwargsInvalid': EXCEPTION_TRANSACTION_PAYLOAD_KWARGS_INVALID,
    'TransactionPayloadNonceInvalid': EXCEPTION_TRANSACTION_PAYLOAD_NONCE_INVALID,
    'TransactionPayloadProcessorMalformed': EXCEPTION_TRANSACTION_PROCESSOR_MALFORMED,
    'TransactionPayloadSenderMalformed': EXCEPTION_TRANSACTION_SENDER_MALFORMED,
    'TransactionPayloadStampSuppliedInvalid': EXCEPTION_TRANSACTION_PAYLOAD_STAMPS_SUPPLIED_INVALID
}

class TransactionMetadataInvalid(Exception):
    pass

class TransactionMetadataSignatureMalformed(Exception):
    pass

class TransactionPayloadInvalid(Exception):
    pass

class TransactionPayloadContractInvalid(Exception):
    pass

class TransactionPayloadFunctionInvalid(Exception):
    pass

class TransactionPayloadKwargsInvalid(Exception):
    pass

class TransactionPayloadNonceInvalid(Exception):
    pass

class TransactionPayloadProcessorMalformed(Exception):
    pass

class TransactionPayloadSenderMalformed(Exception):
    pass

class TransactionPayloadStampSuppliedInvalid(Exception):
    pass


def validate_transaction_structure(transaction: dict) -> bool:
    metadata = transaction.get('metadata')
    if not isinstance(metadata, dict):
        raise TransactionMetadataInvalid(EXCEPTION_TRANSACTION_METADATA_INVALID)

    metadata_signature = metadata.get('signature')
    if not hash_is_sha256_signature(signature=metadata_signature):
        raise TransactionMetadataSignatureMalformed(EXCEPTION_TRANSACTION_METADATA_SIGNATURE_MALFORMED)

    payload = transaction.get('payload')
    if not isinstance(payload, dict):
        raise TransactionPayloadInvalid(EXCEPTION_TRANSACTION_PAYLOAD_INVALID)

    payload_contract = payload.get('contract')
    if not isinstance(payload_contract, str):
        raise TransactionPayloadContractInvalid(EXCEPTION_TRANSACTION_PAYLOAD_CONTRACT_INVALID)

    payload_function = payload.get('function')
    if not isinstance(payload_function, str):
        raise TransactionPayloadFunctionInvalid(EXCEPTION_TRANSACTION_PAYLOAD_FUNCTION_INVALID)

    payload_kwargs = payload.get('kwargs')
    if not isinstance(payload_kwargs, dict):
        raise TransactionPayloadKwargsInvalid(EXCEPTION_TRANSACTION_PAYLOAD_KWARGS_INVALID)

    payload_nonce = payload.get('nonce')
    if not isinstance(payload_nonce, int) or payload_nonce < 0:
        raise TransactionPayloadNonceInvalid(EXCEPTION_TRANSACTION_PAYLOAD_NONCE_INVALID)

    payload_processor = payload.get('processor')
    if not hash_is_sha256(hash_str=payload_processor):
        raise TransactionPayloadProcessorMalformed(EXCEPTION_TRANSACTION_PROCESSOR_MALFORMED)

    payload_sender = payload.get('sender')
    if not hash_is_sha256(hash_str=payload_sender):
        raise TransactionPayloadSenderMalformed(EXCEPTION_TRANSACTION_SENDER_MALFORMED)

    payload_stamps_supplied = payload.get('stamps_supplied')
    if not isinstance(payload_stamps_supplied, int) or payload_stamps_supplied < 0:
        raise TransactionPayloadStampSuppliedInvalid(EXCEPTION_TRANSACTION_PAYLOAD_STAMPS_SUPPLIED_INVALID)

    return True


def verify_block(block: dict, old_block: bool = False) -> bool:
    log = get_logger('BLOCK VALIDATOR')

    try:
        validate_block_structure(block=block)
        is_genesis_block = block.get('genesis') is not None
        if is_genesis_block:
            validate_genesis_hashes(block=block)
            validate_genesis_signatures(block=block)
        else:
            validate_all_hashes(block=block)
            validate_all_signatures(block=block)
            validate_all_proof_signatures(block=block, old_block=old_block)

            if not old_block:
                validate_block_consensus(block=block)

    except Exception as err:
        log.error(err)
        return False

    return True

def validate_all_hashes(block: dict) -> bool:
    if not verify_block_hash(block=block):
        raise BlockHashMalformed(EXCEPTION_BLOCK_HASH_MALFORMED)

    processed_transaction = block.get('processed')
    if not verify_processed_transaction_hash(processed_transaction=processed_transaction):
        raise ProcessedTxHashMalformed(EXCEPTION_PROCESSED_TX_HASH_MALFORMED)

    return True

def verify_block_hash(block) -> bool:
    block_hash = block_hash_from_block(
        hlc_timestamp=block.get('hlc_timestamp'),
        block_number=block.get('number'),
        previous_block_hash=block.get('previous')
    )

    return block_hash == block.get('hash')

def verify_processed_transaction_hash(processed_transaction) -> bool:
    tx_hash = tx_hash_from_tx(
        tx=processed_transaction.get('transaction')
    )

    return tx_hash == processed_transaction.get('hash')


def validate_all_signatures(block: dict, old_block: bool = False) -> bool:
    processed = block.get('processed')
    transaction = processed.get('transaction')

    if not verify_transaction_signature(transaction=transaction):
        raise TransactionMetadataSignatureMalformed(EXCEPTION_TRANSACTION_METADATA_SIGNATURE_MALFORMED)

    if not verify_origin_signature(block=block):
        raise BlockOriginSignatureMalformed(EXCEPTION_BLOCK_ORIGIN_SIGNATURE_MALFORMED)

    if not old_block:
        block_num = block.get('number')
        print(f"Verifying Minter for {block_num}, old_block: {old_block} ")
        if not verify_minter_signature(deepcopy(block)):
            raise BlockMinterSignatureMalformed(EXCEPTION_BLOCK_MINTER_SIGNATURE_MALFORMED)

    return True

def validate_all_proof_signatures(block: dict, old_block: bool = False) -> bool:
    if not verify_proofs(block=block, old_block=old_block):
        raise BlockProofMalformed(EXCEPTION_BLOCK_PROOF_MALFORMED)

    return True

def verify_minter_signature(block):
    try:
        signature = block['minted']['signature']
        minter = block['minted']['minter']
        del block['minted']

        valid = verify(vk=minter, msg=encode(block), signature=signature)
        return valid
    except Exception as err:
        print(err)
        return False

def verify_transaction_signature(transaction: dict) -> bool:
    try:
        signature = transaction['metadata'].get('signature')
        payload = format_dictionary(transaction.get('payload'))
        message = encode(payload)
        sender = payload.get('sender')

        valid = verify(vk=sender, msg=message, signature=signature)
        return valid
    except Exception as err:
        print(err)
        return False

def verify_origin_signature(block: dict) -> bool:
    try:
        hlc_timestamp = block.get('hlc_timestamp')

        signature = block['origin'].get('signature')
        sender = block['origin'].get('sender')

        transaction = block['processed'].get('transaction')

        tx_hash = tx_hash_from_tx(tx=transaction)
        message = f'{tx_hash}{hlc_timestamp}'

        valid = verify(vk=sender, msg=message, signature=signature)
        return valid
    except Exception as err:
        print(err)
        return False

def verify_genesis_origin_signature(block: dict) -> bool:
    try:
        sender = block['origin'].get('sender')
        genesis_state_changes = block.get('genesis')
        genesis_state_changes.sort(key=lambda x: x.get('key'))
        message = hash_genesis_block_state_changes(state_changes=genesis_state_changes)
        signature = block['origin'].get('signature')

        valid = verify(vk=sender, msg=message, signature=signature)
        return valid
    except Exception as err:
        print(err)
        return False

def verify_proofs(block: dict, old_block: bool = False) -> bool:
    tx_result = block.get('processed')
    rewards = block.get('rewards')
    hlc_timestamp = block.get('hlc_timestamp')

    proofs = block.get('proofs')

    for proof in proofs:
        if old_block:
            if not verify_proof_signature_old(proof=proof, tx_result=tx_result, rewards=rewards, hlc_timestamp=hlc_timestamp):
                return False
        else:
            if not verify_proof_signature(proof=proof, tx_result=tx_result, rewards=rewards, hlc_timestamp=hlc_timestamp):
                return False

    return True

def verify_proof_signature(proof: dict, tx_result: str, rewards=[], hlc_timestamp=str) -> bool:
    try:
        signature = proof.get('signature')
        signer = proof.get('signer')

        tx_result_hash=tx_result_hash_from_tx_result_object(
            tx_result=tx_result,
            hlc_timestamp=hlc_timestamp,
            rewards=rewards
        )

        message = create_proof_message_from_proof(
            tx_result_hash=tx_result_hash,
            proof=proof
        )

        valid = verify(vk=signer, msg=message, signature=signature)
        return valid
    except Exception as err:
        print(err)
        return False

def verify_proof_signature_old(proof: dict, tx_result: str, rewards: dict, hlc_timestamp: str) -> bool:
    try:
        signature = proof.get('signature')
        signer = proof.get('signer')

        message = tx_result_hash_from_tx_result_object(
            tx_result=tx_result,
            hlc_timestamp=hlc_timestamp,
            rewards=rewards
        )

        valid = verify(vk=signer, msg=message, signature=signature)
        return valid
    except Exception as err:
        print(err)
        return False

def validate_genesis_hashes(block: dict):
    if not verify_block_hash(block=block):
        raise BlockHashMalformed(EXCEPTION_BLOCK_HASH_MALFORMED)

    return True

def validate_genesis_signatures(block: dict):
    if not verify_genesis_origin_signature(block=block):
        raise BlockOriginSignatureMalformed(EXCEPTION_BLOCK_ORIGIN_SIGNATURE_MALFORMED)

    return True

def validate_block_consensus(block: dict):
    # This will validate that each proof was created by a node with the proper number of members
    # Then it will validate that block also has the correct number of proofs for 51% consensus
    proofs = block.get('proofs')
    member_list_hashes = [proof['members_list_hash'] for proof in proofs]

    most_common_members_list_hash = max(set(member_list_hashes), key=member_list_hashes.count)
    consensus_member_string_count = member_list_hashes.count(most_common_members_list_hash)
    num_of_members = next((proof['num_of_members'] for proof in proofs if proof['members_list_hash'] == most_common_members_list_hash), 0)
    proofs_needed = num_of_members // 2 + 1

    if consensus_member_string_count < proofs_needed:
        raise BlockProofsInvalidConsensus(EXCEPTION_BLOCK_PROOFS_INVALID_CONSENSUS)


def hash_is_sha256(hash_str: str):
    if not isinstance(hash_str, str):
        return False

    try:
        int(hash_str, 16)
    except:
        return False

    return len(hash_str) == 64

def hash_is_sha256_signature(signature: str):
    if not isinstance(signature, str):
        return False

    try:
        int(signature, 16)
    except:
        return False

    return len(signature) == 128

def is_iso8601_hlc_timestamp(hlc_timestamp: str) -> bool:
    if not isinstance(hlc_timestamp, str):
        return False

    hlc_timestamp = hlc_timestamp.split("_")[0]

    try:
        last_dot = hlc_timestamp.rindex('.')
        zone_sep = hlc_timestamp.index('Z') if 'Z' in hlc_timestamp else hlc_timestamp.index('+')
        decimals_str = hlc_timestamp[last_dot:zone_sep]
        s_clean = hlc_timestamp.replace(decimals_str, '')
        dt = parse_date(s_clean)
        # rounding discards nothing, just to int
        seconds = round(dt.timestamp())
        decimals_str = decimals_str.replace('.', '').ljust(9, '0')
        full_str = str(seconds) + decimals_str
        return int(full_str)
    except:
        return False

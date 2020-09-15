from lamden.formatting.primatives import *

TRANSACTION_PAYLOAD_RULES = {
    'sender': vk_is_formatted,
    'processor': vk_is_formatted,
    'nonce': number_is_formatted,
    'stamps_supplied': number_is_formatted,
    'contract': identifier_is_formatted,
    'function': identifier_is_formatted,
    'kwargs': kwargs_are_formatted
}

TRANSACTION_METADATA_RULES = {
    'signature': signature_is_formatted,
    'timestamp': number_is_formatted
}

TRANSACTION_RULES = {
    'metadata': TRANSACTION_METADATA_RULES,
    'payload': TRANSACTION_PAYLOAD_RULES
}

TRANSACTION_OUTPUT_RULES = {
    'hash': vk_is_formatted,
    'result': is_string,
    'stamps_used': number_is_formatted,
    'state': kwargs_are_formatted,
    'status': number_is_formatted,
    'transaction': TRANSACTION_RULES,
}

MERKLE_RULES = {
    'signature': signature_is_formatted,
    'leaves': vk_is_formatted
}

SUBBLOCK_CONTENDER_RULES = {
    'input_hash': vk_is_formatted,
    'transactions': TRANSACTION_OUTPUT_RULES,
    'merkle_tree': MERKLE_RULES,
    'signer': vk_is_formatted,
    'subblock': number_is_formatted,
    'previous': vk_is_formatted
}

SUBBLOCK_RULES = {
    'input_hash': vk_is_formatted,
    'transactions': TRANSACTION_OUTPUT_RULES,
    'merkle_leaves': vk_is_formatted,
    'signatures': signature_is_formatted,
    'subblock': number_is_formatted,
    'previous': vk_is_formatted
}

BLOCK_RULES = {
    'hash': vk_is_formatted,
    'number': number_is_formatted,
    'previous': vk_is_formatted,
    'subblocks': SUBBLOCK_RULES
}

ROUTER_MESSAGE_RULES = {
    'service': is_string,
    'msg': is_dict
}

JOIN_MESSAGE_RULES = {
    'vk': vk_is_formatted,
    'ip': is_tcp_or_ipc_string
}

# proof = signed hash of proof tuple
PROOF_MESSAGE_RULES = {
    'signature': signature_is_formatted,
    'vk': vk_is_formatted,
    'timestamp': number_is_formatted,
    'ip': is_tcp_or_ipc_string
}


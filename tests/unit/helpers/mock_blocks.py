import hashlib
from lamden.nodes.hlc import HLC_Clock
from lamden.utils import hlc
from lamden.crypto.canonical import tx_result_hash_from_tx_result_object, create_proof_message_from_tx_results
from lamden.crypto.wallet import Wallet

GENESIS_BLOCK = {
    'hash': '2bb4e112aca11805538842bd993470f18f337797ec3f2f6ab02c47385caf088e',
    'number': "0",
    'hlc_timestamp': '0000-00-00T00:00:00.000000000Z_0',
    'previous': '0000000000000000000000000000000000000000000000000000000000000000',
    'genesis': [
        {'key': 'currency.balances:9fb2b57b1740e8d86ecebe5bb1d059628df02236b69ed74de38b5e9d71230286', 'value': 100000000}
    ],
    'origin': {
        'sender': '9fb2b57b1740e8d86ecebe5bb1d059628df02236b69ed74de38b5e9d71230286',
        'signature': '82beb173f13ecc239ac108789b45428110ff56a84a3d999c0a1251a22974ea9b426ef61b13e04819d19556657448ba49a2f37230b8450b4de28a1a3cc85a3504'
    }
}


def create_proofs(tx_result, hlc_timestamp, rewards, members):
    proofs = list()

    members_list = [member_wallet.verifying_key for member_wallet in members]

    for member_wallet in members:
        proof_details = create_proof_message_from_tx_results(
            tx_result=tx_result,
            hlc_timestamp=hlc_timestamp,
            rewards=rewards,
            members=members_list,
        )

        signature = member_wallet.sign(proof_details.get('message'))

        proof = {
            'signature': signature,
            'signer': member_wallet.verifying_key,
            'members_list_hash': proof_details.get('members_list_hash'),
            'num_of_members': proof_details.get('num_of_members'),
        }

        proofs.append(proof)

        return proofs

def generate_mock_block(prev_block_hlc, prev_block_hash, members):
    hlc_clock = HLC_Clock()
    hlc_clock.merge_hlc_timestamp(prev_block_hlc)
    hlc_timestamp = hlc_clock.get_new_hlc_timestamp()
    block_num = hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp)

    h = hashlib.sha3_256()

    h.update('{}{}{}'.format(hlc_timestamp, block_num, prev_block_hash).encode())

    hash_result = hashlib.sha3_256()
    hash_result.update('{}'.format(hlc_timestamp).encode())
    hash_result = hash_result.hexdigest()

    block = {
        "hash": h.hexdigest(),
        "number": str(block_num),
        "hlc_timestamp": hlc_timestamp,
        "previous": prev_block_hash,
        "proofs": [],
        'processed': {
            "hash": hash_result,
            "hlc_timestamp": hlc_timestamp,
            "result": "None",
            "stamps_used": 18,
            "state": [
                {
                    "key": "lets",
                    "value": "go"
                },
                {
                    "key": "blue",
                    "value": "jays"
                }
            ],
            "status": 0,
            "transaction": {
                "metadata": {
                    "signature": "some sig"
                },
                "payload": None
            },
            "rewards": [],
            "origin": {
                "signature": "some sig",
                "signer": "some signer"
            }
        },
        "origin": {

        }
    }

    block['proofs'] = create_proofs(
            tx_result=hash_result,
            hlc_timestamp=hlc_timestamp,
            rewards=[],
            members=members
        )

    return block



def generate_blocks(number_of_blocks, prev_block_hash, prev_block_hlc):
    members = [Wallet(), Wallet()]

    blocks = []
    for i in range(number_of_blocks):
        block = generate_mock_block(
            prev_block_hash=prev_block_hash,
            prev_block_hlc=prev_block_hlc,
            members=members
        )

        prev_block_hash = block.get('hash')
        prev_block_hlc = block.get('hlc_timestamp')

        blocks.append(block)

    return blocks



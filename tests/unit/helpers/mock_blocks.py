import hashlib
from lamden.nodes.hlc import HLC_Clock
from lamden.utils import hlc

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

def generate_mock_block(prev_block_hlc, prev_block_hash):
    hlc_clock = HLC_Clock()
    hlc_clock.merge_hlc_timestamp(prev_block_hlc)
    hlc_timestamp = hlc_clock.get_new_hlc_timestamp()
    block_num = hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp)

    h = hashlib.sha3_256()

    h.update('{}{}{}'.format(hlc_timestamp, block_num, prev_block_hash).encode())

    hash = hashlib.sha3_256()
    hash.update('{}'.format(hlc_timestamp).encode())
    return  {
        "hash": h.hexdigest(),
        "number": block_num,
        "hlc_timestamp": hlc_timestamp,
        "previous": prev_block_hash,
        "proofs": [
            {
                'signature': "mock_sig",
                'signer': "mock_node"
            },
        ],
        'processed': {
            "hash": "mock_" + hash.hexdigest(),
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
        }
    }
}


def generate_blocks(number_of_blocks, prev_block_hash, prev_block_hlc):

    blocks = []
    for i in range(number_of_blocks):
        block = generate_mock_block(
            prev_block_hash=prev_block_hash,
            prev_block_hlc=prev_block_hlc
        )

        prev_block_hash = block.get('hash')
        prev_block_hlc = block.get('hlc_timestamp')

        blocks.append(block)

    return blocks



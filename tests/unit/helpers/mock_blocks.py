import hashlib
from lamden.nodes.hlc import HLC_Clock
from lamden.utils import hlc

def generate_mock_block(prev_block_hlc, prev_block_hash):
    hlc_clock = HLC_Clock()
    hlc_clock.merge_hlc_timestamp(prev_block_hlc)
    hlc_timestamp = hlc_clock.get_new_hlc_timestamp()
    block_num = hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp)

    h = hashlib.sha3_256()

    h.update('{}{}{}'.format(hlc_timestamp, block_num, prev_block_hash).encode())

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
            "hash": "mock_aa7304d6bc9871ba0ef530e5e8b6dd7331f6c3ae7a58fa3e482c77275f3",
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

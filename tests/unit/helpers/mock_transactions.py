DEFAULT_BLOCK = '0000000000000000000000000000000000000000000000000000000000000000'
from lamden.crypto.transaction import build_transaction
from lamden.crypto.canonical import tx_result_hash_from_tx_result_object, tx_hash_from_tx, block_from_subblocks
from lamden.crypto.wallet import Wallet
import json
import zmq.asyncio
from lamden.nodes.hlc import HLC_Clock
from lamden.nodes.processing_queue import TxProcessingQueue
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
from contracting.execution.executor import Executor
from lamden import rewards
from lamden.contracts import sync

def generate_blocks(number_of_blocks):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        new_block = block_from_subblocks(
            subblocks=[],
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks

def get_new_currency_tx(wallet=None, to=None, amount=None, processor=None):
    txb = build_transaction(
        wallet=wallet or Wallet(),
        contract="currency",
        function="transfer",
        kwargs={
            'to': to or Wallet().verifying_key,
            'amount': {'__fixed__': amount or '100.5'},
        },
        nonce=0,
        processor=processor or '0' * 64,
        stamps=50
    )
    return json.loads(txb)

def get_new_vote_tx(type, vk, sender):
    txb = build_transaction(
        wallet=sender,
        contract=f'{type}s',
        function="transfer",
        kwargs={
            'to': to or Wallet().verifying_key,
            'amount': {'__fixed__': amount or '100.5'},
        },
        nonce=0,
        processor='0' * 64,
        stamps=50
    )
    return json.loads(txb)

def get_introduce_motion_tx(policy, motion, vk, wallet=None, nonce=None):
    txb = build_transaction(
        wallet=wallet or Wallet(),
        contract='election_house',
        function='vote',
        kwargs={
            'policy': policy,
            'value': ['introduce_motion', motion, vk]
        },
        nonce=nonce or 0,
        processor=wallet.verifying_key or '0' * 64,
        stamps=50
    )
    return json.loads(txb)

def get_vote_tx(policy, vote, wallet=None, nonce=None):
    txb = build_transaction(
        wallet=wallet or Wallet(),
        contract='election_house',
        function='vote',
        kwargs={
            'policy': policy,
            'value': ['vote_on_motion', vote]
        },
        nonce=nonce or 0,
        processor=wallet.verifying_key or '0' * 64,
        stamps=50
    )
    return json.loads(txb)

def get_tx_message(wallet=None, to=None, amount=None, tx=None, node_wallet=None):
    wallet = wallet or Wallet()

    if tx is None:
        tx = get_new_currency_tx(
            wallet=wallet,
            to=to,
            amount=amount
        )


    hlc_clock = HLC_Clock()
    hlc_timestamp = hlc_clock.get_new_hlc_timestamp()
    tx_hash = tx_hash_from_tx(tx=tx)

    signature = wallet.sign(f'{tx_hash}{hlc_timestamp}')

    return {
        'tx': tx,
        'hlc_timestamp': hlc_timestamp,
        'signature': signature,
        'sender': wallet.verifying_key
    }

def get_processing_results(tx_message, driver=None, node_wallet=None, node=None):
    if node:
        processing_results = node.main_processing_queue.process_tx(tx=tx_message)
    else:
        driver = driver or ContractDriver()
        client = ContractingClient(driver=driver)

        sync.submit_from_genesis_json_file(client=client)

        main_processing_queue = TxProcessingQueue(
            testing=True,
            debug=True,
            driver=driver,
            client=client,
            wallet=node_wallet or Wallet(),
            hlc_clock=HLC_Clock(),
            processing_delay=lambda: 0,
            get_last_hlc_in_consensus=lambda: "0",
            stop_node=lambda: True,
            reprocess=lambda: True,
            check_if_already_has_consensus=lambda: False,
            pause_all_queues=lambda: True,
            unpause_all_queues=lambda: True
        )
        main_processing_queue.distribute_rewards = lambda total_stamps_to_split, contract_name: True

        processing_results = main_processing_queue.process_tx(tx=tx_message)
        hlc_timestamp = processing_results.get('hlc_timestamp')
        tx_result = processing_results.get('tx_result')
        tx_result_hash = tx_result_hash_from_tx_result_object(tx_result=tx_result, hlc_timestamp=hlc_timestamp)
        processing_results['proof']['tx_result_hash'] = tx_result_hash
    return processing_results


def get_new_block(
        signer="testuser",
        hash=64 * f'1',
        number=1,
        hlc_timestamp='1',
        to=None,
        amount=None,
        sender=None,
        tx=None,
        state=None
):
    blockinfo = {
        "hash": "hashed(hlc_timestamp + number + previous_hash)",
        "number": number,
        "hlc_timestamp": "some hlc_timestamp",
        "previous": "0000000000000000000000000000000000000000000000000000000000000000",
        "proofs": [
            {
                'signature': "node_1_sig",
                'signer': "node_1_vk"
            },
            {
                'signature': "node_5_sig",
                'signer': "node_5_vk"
            },
            {
                'signature': "node_25_sig",
                'signer': "node_25_vk"
            }
        ],
        'processed': {
            "hash": "467ebaa7304d6bc9871ba0ef530e5e8b6dd7331f6c3ae7a58fa3e482c77275f3",
            "hlc_timestamp": hlc_timestamp,
            "result": "None",
            "stamps_used": 18,
            "state": state or [
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
            "transaction": tx or get_new_tx(to=to, amount=amount, sender=sender)
          }
      }

    return blockinfo

def get_new_processing_result(result_hash, tx_results, wallet, hlc_timestamp):
    return {
        'result_hash': result_hash,
        'hlc_timestamp': hlc_timestamp,
        'signature': 'd04fd24c0547895a30cfb6d524e515e3955346b1b50a23ebac20b17e2cd3a468f0bf59f0c84e00119ef84cd14a9ffdd730434ada404c37207db29640594f1c0d',
        'sender': wallet.verifying_key,
        'processing_results': {
            'hlc_timestamp': hlc_timestamp,
            'input_hash': 'b5a72717df59dc1d0fc4848d5f35d6eb3116276550c776211322bdaadc9a45d8',
            'merkle_leaves': ['e1ae1a8f8a0330dfbbcd2af6e4737cad67f33687d3510a738b7676942d91721d'],
            'signatures': [
                {
                    'signature': '92edae10286aa9033328a561f5b97986936bc24b88d45491c5c0b8ce805db80013a53833a8f9bef9c661d716e81b4f7c733b44acbcd33322640063cfe0bb7102',
                    'signer': wallet.verifying_key
                }
            ],
            'subblock': 0,
            'transactions': [tx_results]
        },
        'proof': {
            'node_vk': wallet.verifying_key,
            'signer': wallet.verifying_key,
            'tx_result_hash': result_hash
        },
        'tx_result': {
            'transaction': 'sample_transaction'
        },
        'tx_message': {
            'signature': 'sample_signature'
        }
    }

def get_tx_results(hlc_timestamp, state, kwargs, sender):
    return {
        'hash': 'c1d084f61936c766746d4a4ec9f5a6c256ad6f5c68ca513270b5a38b4e4dd756',
        'hlc_timestamp': hlc_timestamp,
        'result': "None",
        'stamps_used': 1,
        'state': state,
        'status': 1,
        'transaction': {
            'metadata': {
                'signature': '7eac4c17004dced6d079e260952fffa7750126d5d2c646ded886e6b1ab4f6da1e22f422aad2e1954c9529cfa71a043af8c8ef04ccfed6e34ad17c6199c0eba0e',
                'timestamp': 1624049397
            },
            'payload': {
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': kwargs,
              'nonce': 0,
              'processor': '92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e',
              'sender': sender,
              'stamps_supplied': 100
            }

        }
    }

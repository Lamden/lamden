from contracting.execution.executor import Executor
from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import encode, safe_repr
from cilantro.crypto.canonical import tx_hash_from_tx, format_dictionary, merklize
from cilantro.logger.base import get_logger
from datetime import datetime

log = get_logger('EXE')


def execute_tx(executor: Executor, transaction, stamp_cost, environment: dict={}):
    # Deserialize Kwargs. Kwargs should be serialized JSON moving into the future for DX.

    output = executor.execute(
        sender=transaction['payload']['sender'],
        contract_name=transaction['payload']['contract'],
        function_name=transaction['payload']['function'],
        stamps=transaction['payload']['stamps_supplied'],
        stamp_cost=stamp_cost,
        kwargs=transaction['payload']['kwargs'],
        environment=environment,
        auto_commit=False
    )

    if output['status_code'] == 0:
        log.info(f'TX executed successfully. '
                 f'{output["stamps_used"]} stamps used. '
                 f'{len(output["writes"])} writes. '
                 f'Result = {output["result"]}')
    else:
        log.error(f'TX executed unsuccessfully. '
                  f'{output["stamps_used"]} stamps used. '
                  f'{len(output["writes"])} writes.'
                  f' Result = {output["result"]}')

    log.debug(output['writes'])

    tx_hash = tx_hash_from_tx(transaction)

    # Only apply the writes if the tx passes
    if output['status_code'] == 0:
        writes = [{'key': k, 'value': v} for k, v in output['writes'].items()]
    else:
        writes = {}

    tx_output = {
        'hash': tx_hash,
        'transaction': transaction,
        'status': output['status_code'],
        'state': writes,
        'stamps_used': output['stamps_used'],
        'result': safe_repr(output['result'])
    }

    tx_output = format_dictionary(tx_output)

    executor.driver.pending_writes.clear() # add

    return tx_output


def generate_environment(driver, timestamp, input_hash, bhash='0' * 64, num=1):
    now = Datetime._from_datetime(
        datetime.utcfromtimestamp(timestamp)
    )

    return {
        'block_hash': bhash,
        'block_num': num,
        '__input_hash': input_hash,  # Used for deterministic entropy for random games
        'now': now
    }


def execute_tx_batch(executor, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1):
    environment = generate_environment(driver, timestamp, input_hash, bhash, num)

    # Each TX Batch is basically a subblock from this point of view and probably for the near future
    tx_data = []
    for transaction in batch['transactions']:
        tx_data.append(execute_tx(executor=executor,
                                  transaction=transaction,
                                  environment=environment,
                                  stamp_cost=stamp_cost)
                       )

    return tx_data


def execute_work(executor, driver, work, wallet, previous_block_hash, current_height=0, stamp_cost=20000, parallelism=4):
    # Assume single threaded, single process for now.
    subblocks = []
    i = 0

    for tx_batch in work:
        results = execute_tx_batch(
            executor=executor,
            driver=driver,
            batch=tx_batch,
            timestamp=tx_batch['timestamp'],
            input_hash=tx_batch['input_hash'],
            stamp_cost=stamp_cost,
            bhash=previous_block_hash,
            num=current_height
        )

        if len(results) > 0:
            merkle = merklize([encode(r).encode() for r in results])
            proof = wallet.sign(merkle[0])
        else:
            merkle = merklize([bytes.fromhex(tx_batch['input_hash'])])
            proof = wallet.sign(tx_batch['input_hash'])

        merkle_tree = {
            'leaves': merkle,
            'signature': proof
        }

        sbc = {
            'input_hash': tx_batch['input_hash'],
            'transactions': results,
            'merkle_tree': merkle_tree,
            'signer': wallet.verifying_key,
            'subblock': i % parallelism,
            'previous': previous_block_hash
        }

        sbc = format_dictionary(sbc)

        subblocks.append(sbc)
        i += 1

    return subblocks

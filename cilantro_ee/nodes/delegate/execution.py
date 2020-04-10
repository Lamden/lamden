from contracting.execution.executor import Executor
from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import decode
from contracting.db.driver import encode_kv
from cilantro_ee.crypto.canonical import build_sbc_from_work_results, tx_hash_from_tx
from cilantro_ee.logger.base import get_logger
import os
import capnp
from datetime import datetime
import hashlib
import heapq
import cilantro_ee.messages.capnp_impl.capnp_struct as schemas

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

log = get_logger('EXE')


def execute_tx(executor: Executor, transaction, stamp_cost, environment: dict={}, debug=True):
    # Deserialize Kwargs. Kwargs should be serialized JSON moving into the future for DX.
    kwargs = decode(transaction.payload.kwargs)

    output = executor.execute(
        sender=transaction.payload.sender.hex(),
        contract_name=transaction.payload.contractName,
        function_name=transaction.payload.functionName,
        stamps=transaction.payload.stampsSupplied,
        stamp_cost=stamp_cost,
        kwargs=kwargs,
        environment=environment,
        auto_commit=False
    )

    if debug:
        log.error(output)

    deltas = []
    for k, v in output['writes'].items():
        key, value = encode_kv(k, v)
        d = transaction_capnp.Delta.new_message(key=key, value=value)
        deltas.append(d)

    tx_hash = tx_hash_from_tx(transaction)

    # Encode deltas into a Capnp struct
    tx_output = transaction_capnp.TransactionData.new_message(
        hash=tx_hash,
        transaction=transaction,
        status=output['status_code'],
        state=deltas,
        stampsUsed=output['stamps_used']
    )

    executor.driver.pending_writes.clear()

    return tx_output


def generate_environment(driver, timestamp, input_hash):
    now = Datetime._from_datetime(
        datetime.utcfromtimestamp(timestamp)
    )

    return {
        'block_hash': driver.latest_block_hash,
        'block_num': driver.latest_block_num + 1,
        '__input_hash': input_hash,  # Used for deterministic entropy for random games
        'now': now
    }


def execute_tx_batch(executor, driver, batch, timestamp, input_hash, stamp_cost):
    environment = generate_environment(driver, timestamp, input_hash)

    # Each TX Batch is basically a subblock from this point of view and probably for the near future
    tx_data = []
    for transaction in batch.transactions:
        tx_data.append(execute_tx(executor=executor,
                                  transaction=transaction,
                                  environment=environment,
                                  stamp_cost=stamp_cost)
                       )

    return tx_data


def execute_work(executor, driver, work, wallet, previous_block_hash, stamp_cost, parallelism=4):
    # Assume single threaded, single process for now.
    subblocks = []
    i = 0

    while len(work) > 0:
        _, tx_batch = heapq.heappop(work)

        results = execute_tx_batch(
            executor=executor,
            driver=driver,
            batch=tx_batch,
            timestamp=tx_batch.timestamp,
            input_hash=tx_batch.inputHash,
            stamp_cost=stamp_cost
        )

        sbc = build_sbc_from_work_results(
            input_hash=tx_batch.inputHash,
            results=results,
            sb_num=i % parallelism,
            wallet=wallet,
            previous_block_hash=previous_block_hash
        )

        subblocks.append(sbc)
        i += 1

    driver.clear_pending_state()

    return subblocks

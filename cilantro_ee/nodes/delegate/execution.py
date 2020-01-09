from contracting.client import ContractingClient
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.stdlib.bridge.time import Datetime

from cilantro_ee.core.canonical import build_sbc_from_work_results

import os
import capnp
from datetime import datetime
import heapq
import cilantro_ee.messages.capnp_impl.capnp_struct as schemas

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


def execute_tx(client: ContractingClient, transaction, environment: dict={}):
    # Deserialize Kwargs. Kwargs should be serialized JSON moving into the future for DX.
    kwargs = {}
    for entry in transaction.payload.kwargs.entries:
        if entry.value.which() == 'fixedPoint':
            kwargs[entry.key] = ContractingDecimal(entry.value.fixedPoint)  # ContractingDecimal!
        else:
            kwargs[entry.key] = getattr(entry.value, entry.value.which())

    output = client.executor.execute(
        sender=transaction.payload.sender.hex(),
        contract_name=transaction.payload.contractName,
        function_name=transaction.payload.functionName,
        stamps=transaction.payload.stampsSupplied,
        kwargs=kwargs,
        environment=environment,
        auto_commit=False
    )

    # Encode deltas into a Capnp struct
    deltas = [transaction_capnp.Delta.new_message(key=k, value=v) for k, v in output['writes'].items()]
    tx_output = transaction_capnp.TransactionData.new_message(
        transaction=transaction,
        status=output['status_code'],
        state=deltas,
        stampsUsed=output['stamps_used']
    )

    return tx_output


def generate_environment(driver, timestamp, input_hash):
    now = Datetime._from_datetime(
        datetime.utcfromtimestamp(timestamp)
    )

    return {
        'block_hash': driver.latest_block_hash.hex(),
        'block_num': driver.latest_block_num,
        '__input_hash': input_hash,  # Used for deterministic entropy for random games
        'now': now
    }


def execute_tx_batch(client, driver, batch, timestamp, input_hash):
    environment = generate_environment(driver, timestamp, input_hash)

    # Each TX Batch is basically a subblock from this point of view and probably for the near future
    tx_data = []
    for transaction in batch.transactions:
        tx_data.append(execute_tx(client, transaction, environment))

    return tx_data


def execute_work(client, driver, work, wallet, previous_block_hash, parallelism=4):
    # Assume single threaded, single process for now.
    subblocks = []
    i = 0

    while len(work) > 0:
        _, tx_batch = heapq.heappop(work)

        results = execute_tx_batch(
            client=client,
            driver=driver,
            batch=tx_batch,
            timestamp=tx_batch.timestamp,
            input_hash=tx_batch.inputHash
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

    return subblocks

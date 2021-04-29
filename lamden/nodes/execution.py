from contracting.execution.executor import Executor
from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import encode, safe_repr
from lamden.crypto.canonical import tx_hash_from_tx, format_dictionary, merklize
from lamden.logger.base import get_logger
from datetime import datetime

import multiprocessing as mp
import copy
from time import time, sleep
import queue

log = get_logger('EXE')
log.propagate = False

__N_WORKER_PER_DELEGATES__ = 4
__N_DELEGATES__ = 2
__N_WORKER__ = __N_WORKER_PER_DELEGATES__ * __N_DELEGATES__


PoolExecutor = None
stop_cmd = None
pool = []
busy_pool = []

N_TEST = 8
WORKER_SLEEP = 0.0001
RESULT_SLEEP = 0.01
POOL_WAIT_SLEEP = 0.01

TX_RERUN_SLEEP = 1
N_TRY_PER_TX = 3


class TransactionExecutor:
    def execute_tx(self, transaction, stamp_cost, environment: dict={}):
        raise NotImplementedError

    def generate_environment(self, driver, timestamp, input_hash, bhash='0' * 64, num=1):
        raise NotImplementedError

    def execute_tx_batch(self, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1):
        raise NotImplementedError

    def execute_work(self, executor, work, wallet, previous_block_hash, current_height=0, stamp_cost=20000, parallelism=4):
        raise NotImplementedError


class ConflictResolutionExecutor(TransactionExecutor):
    def __init__(self, workers=8):
        self.workers = workers
        self.executor = PoolExecutor

    def execute_tx(self, transaction, stamp_cost, environment: dict = {}, tx_number=0):
        #global PoolExecutor
        #executor = PoolExecutor
        output = self.executor.execute(
            sender=transaction['payload']['sender'],
            contract_name=transaction['payload']['contract'],
            function_name=transaction['payload']['function'],
            stamps=transaction['payload']['stamps_supplied'],
            stamp_cost=stamp_cost,
            kwargs=transaction['payload']['kwargs'],
            environment=environment,
            auto_commit=False
        )

        tx_hash = tx_hash_from_tx(transaction)

        writes = [{'key': k, 'value': v} for k, v in output['writes'].items()]

        tx_output = {
            'hash': tx_hash,
            'transaction': transaction,
            'status': output['status_code'],
            'state': writes,
            'stamps_used': output['stamps_used'],
            'result': safe_repr(output['result']),
            'tx_number': tx_number
        }
        tx_output = format_dictionary(tx_output)
        self.executor.driver.pending_writes.clear()  # add
        return tx_output

    def generate_environment(self, driver, timestamp, input_hash, bhash='0' * 64, num=1):
        now = Datetime._from_datetime(
            datetime.utcfromtimestamp(timestamp)
        )

        return {
            'block_hash': bhash,
            'block_num': num,
            '__input_hash': input_hash,  # Used for deterministic entropy for random games
            'now': now
        }

    def start_pool(self):
        global stop_cmd
        stop_cmd = mp.Value('i', 0)

        for i in range(__N_WORKER__):
            queue_in1 = mp.Queue()
            queue_out1 = mp.Queue()
            p = ProcessThread(queue_in1, queue_out1, stop_cmd, executor=self)
            pool.append(p)
            busy_pool.append(0)
            p.start()

        for i in range(5):
            n_proc = 0
            for i in range(__N_WORKER__):
                if pool[i].is_alive():
                    n_proc += 1
            if n_proc == __N_WORKER__:
                log.info(f" Workers started OK")
                return True
            sleep(1)
        log.error(f" Can't start workers")
        return False

    def execute_tx_batch(self, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1):

        environment = self.generate_environment(driver, timestamp, input_hash, bhash, num)
        set_pool_executor(self.executor)

        global pool
        if len(pool) == 0:
            self.start_pool()
            log.debug(f'Initialyze pool {len(pool)}')

        #work_pool, active_workers = self.get_pool(len(batch['transactions']))
        work_pool, active_workers = self.get_pool(1)
        i = 0
        s = time()
        global result_list2
        result_list2 = []
        log.debug(f"Start Pool len={active_workers}  prc={work_pool}")

        for transaction in batch['transactions']:
            log.debug(f'Transaction {i}   {type(self.executor)}')
            it = (transaction, stamp_cost, environment, i)
            i_prc = work_pool[i % active_workers]
            pool[i_prc].q_in.put(it)
            i += 1

        N_tx = i
        result_list2 = self.wait_tx_result(N_tx, work_pool)
        self.free_pool(work_pool)

        log.debug(f"End of pool. result_list={result_list2}")

        tx_data = copy.deepcopy(result_list2)
        result_list2 = []
        tx_done_ok = [tx['tx_number'] for tx in tx_data]
        tx_bad = [tx['tx_number'] for tx in tx_data if tx['status'] != 0]
        log.debug(f"tx_data={len(tx_data)}  tx_done_ok={tx_done_ok}  tx_bad={tx_bad} duration= {time() - s}")

        if len(tx_bad) > 0:
            self.free_pool(work_pool)
            work_pool, active_workers = self.get_pool(len(tx_bad))

            log.debug(f'Bad transactions {len(tx_bad)}. Try to rerun {active_workers}  {work_pool}')
            sleep(TX_RERUN_SLEEP)
            i = 0
            for transaction in batch['transactions']:
                if i in tx_bad:
                    log.debug(f'rerun Transaction {i}')
                    it = (transaction, stamp_cost, environment, i)
                    i_prc = work_pool[i % active_workers]
                    pool[i_prc].q_in.put(it)

                i += 1
            N_tx_rerun = i
            result_list2 = self.wait_tx_result(N_tx_rerun, work_pool)
            log.debug(f"End of rerun. result_list={result_list2}")
            self.free_pool(work_pool)

            for r in result_list2:
                tx_data.append(r)

        return tx_data

    def execute_work(self, driver, work, wallet, previous_block_hash, current_height=0, stamp_cost=20000,
                     parallelism=4):
        # Assume single threaded, single process for now.
        subblocks = []
        i = 0

        for tx_batch in work:
            results = self.execute_tx_batch(
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

    def get_pool(self, n_needed):
        rez_pool = {}
        cnt = 0
        n_step = 0
        if n_needed > 0:
            if n_needed > __N_WORKER_PER_DELEGATES__:
                n_needed = __N_WORKER_PER_DELEGATES__
            while n_step < 3:
                for i in range(__N_WORKER__):
                    if busy_pool[i] == 0:
                        busy_pool[i] = 1
                        rez_pool[cnt] = i
                        cnt += 1
                    if cnt >= n_needed:
                        break
                if cnt > 0:
                    break
                else:
                    sleep(POOL_WAIT_SLEEP)
                    n_step += 1
        return rez_pool, cnt

    def free_pool(self, rez_pool):
        for k, v in rez_pool.items():
            busy_pool[v] = 0

    def stop_pool(self):
        if pool is None:
            return
        global stop_cmd
        stop_cmd.value = 1
        for i in range(__N_WORKER__):
            pool[i].join()
        log.info(f" Workers stopped OK")

    def wait_tx_result(self, N_tx, work_pool):
        active_workers = len(work_pool)
        kk = 0
        k_step = 0
        k_wait = N_tx * N_TRY_PER_TX
        rez = []
        while k_step < k_wait:
            for i_tx in range(N_tx):
                try:
                    k_step += 1
                    i_prc = work_pool[i_tx % active_workers]
                    r = pool[i_prc].q_out.get_nowait()
                    if r is not None:
                        rez.append(r)
                        kk += 1
                except queue.Empty:
                    sleep(RESULT_SLEEP)
            if kk >= N_tx:
                break
        return rez


class ProcessThread(mp.Process):
    def __init__(self, q_in, q_out, s_stop, executor: ConflictResolutionExecutor):
        super(ProcessThread, self).__init__()
        self.q_in = q_in
        self.q_out = q_out
        self.s_stop = s_stop
        self.executor = executor

    def run(self):
        while 1:
            if (int(self.s_stop.value) == 1):
                # print("Process stopped")
                break
            # print("Process run")
            try:
                x = self.q_in.get_nowait()
                if x is not None:
                    # work()
                    try:
                        tx_input = x
                        output = self.executor.execute_tx(tx_input[0], tx_input[1], environment= tx_input[2], tx_number=tx_input[3])
                        self.q_out.put(output)
                    except Exception as err:
                        log.error(f"Worker stopped after exception={err}")
                        break
            except queue.Empty:
                sleep(WORKER_SLEEP)
        # print("Process exit")
        return


def set_pool_executor(executor: Executor):
    global PoolExecutor
    PoolExecutor = executor


class SerialExecutor(TransactionExecutor):
    def __init__(self, executor: Executor):
        self.executor = executor

    def execute_tx(self, transaction, stamp_cost, environment: dict = {}):
        # Deserialize Kwargs. Kwargs should be serialized JSON moving into the future for DX.

        # Add AUXILIARY_SALT for more randomness

        environment['AUXILIARY_SALT'] = transaction['metadata']['signature']

        balance = self.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[transaction['payload']['sender']],
            mark=False
        )

        output = self.executor.execute(
            sender=transaction['payload']['sender'],
            contract_name=transaction['payload']['contract'],
            function_name=transaction['payload']['function'],
            stamps=transaction['payload']['stamps_supplied'],
            stamp_cost=stamp_cost,
            kwargs=transaction['payload']['kwargs'],
            environment=environment,
            auto_commit=False
        )

        self.executor.driver.pending_writes.clear()

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
            # Calculate only stamp deductions
            to_deduct = output['stamps_used'] / stamp_cost
            new_bal = 0
            try:
                new_bal = balance - to_deduct
            except TypeError:
                pass

            writes = [{
                'key': 'currency.balances:{}'.format(transaction['payload']['sender']),
                'value': new_bal
            }]

        tx_output = {
            'hash': tx_hash,
            'transaction': transaction,
            'status': output['status_code'],
            'state': writes,
            'stamps_used': output['stamps_used'],
            'result': safe_repr(output['result'])
        }

        tx_output = format_dictionary(tx_output)

        return tx_output

    def generate_environment(self, driver, timestamp, input_hash, bhash='0' * 64, num=1):
        now = Datetime._from_datetime(
            datetime.utcfromtimestamp(timestamp)
        )

        return {
            'block_hash': bhash,
            'block_num': num,
            '__input_hash': input_hash,  # Used for deterministic entropy for random games
            'now': now,
        }

    def execute_tx_batch(self, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1):
        environment = self.generate_environment(driver, timestamp, input_hash, bhash, num)

        # Each TX Batch is basically a subblock from this point of view and probably for the near future
        tx_data = []
        '''
        for transaction in batch['transaction']:
            tx_data.append(self.execute_tx(transaction=transaction,
                                           environment=environment,
                                           stamp_cost=stamp_cost)
                           )
        '''

        tx_data.append(self.execute_tx(transaction=batch['tx'],
                                       environment=environment,
                                       stamp_cost=stamp_cost)
                       )

        return tx_data

    def execute_work(self, driver, work, wallet, previous_block_hash, current_height=0, stamp_cost=20000,
                     parallelism=4):
        # Assume single threaded, single process for now.
        subblocks = []
        i = 0

        for tx_batch in work:
            results = self.execute_tx_batch(
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

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

# __N_WORKER_PER_DELEGATES__ = 4
# __N_DELEGATES__ = 2
# __N_WORKER__ = __N_WORKER_PER_DELEGATES__ * __N_DELEGATES__
__N_WORKER_PER_DELEGATES__ = 8
__N_WORKER__ = 8



PoolExecutor = None
stop_cmd = None
pool = []
busy_pool = []

N_TEST = 8
WORKER_SLEEP = 0.0001
RESULT_SLEEP = 0.01
POOL_WAIT_SLEEP = 0.1
POOL_WAIT_STEPS = 1000

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
        self.work_pool = None
        self.active_workers = None

    def execute_tx(self, transaction, stamp_cost, environment: dict = {}, tx_number=0, ini_writes=None):
        #global PoolExecutor
        #executor = PoolExecutor
        if ini_writes is not None:
            log.debug(f'ini_writes={ini_writes} cash ={self.executor.driver.cache}')
            p_cashe = self.executor.driver.cache
            for k in ini_writes:
                if k in p_cashe:
                    log.debug(f"deleted {k} from cash")
                    del p_cashe[k]
            return None
        self.executor.driver.reads.clear()
        self.executor.driver.pending_writes.clear()
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
        log.debug(output)

        tx_hash = tx_hash_from_tx(transaction)

        writes = [{'key': k, 'value': v} for k, v in output['writes'].items()]
        p_writes = self.executor.driver.pending_writes
        tx_output = {
            'hash': tx_hash,
            'transaction': transaction,
            'status': output['status_code'],
            'state': writes,
            'stamps_used': output['stamps_used'],
            'result': safe_repr(output['result']),
            'tx_number': tx_number,
            'p_writes': p_writes,
            'reads': output['reads']
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

    def check_conflict2(self, rez_batch):
        tx_bad0 = list()
        tx_index = {}
        i1a = 0
        rez_ok = []
        for tx_data0 in rez_batch:
            i2a = 0
            for tx0 in tx_data0:
                tx_hash = tx0['hash']
                conflict = False
                i1b = 0
                for tx_data in rez_batch:
                    i2b = 0
                    for tx in tx_data:
                        if tx_hash != tx['hash']:
                            for k, v in tx['p_writes'].items():
                                if v is not None:
                                    if k in tx0['reads']:
                                        log.debug(f"reads conflict found: {k}")
                                        conflict = True
                                        break
                                    if k in tx0['p_writes']:
                                        log.debug(f"p_writes conflict found: {k}")
                                        conflict = True
                                        break
                        if conflict:
                            if tx['hash'] not in tx_bad0:
                                tx_bad0.append(tx['hash'])
                                tx_index[tx['hash']] = (i1b, i2b)
                            if tx_hash not in tx_bad0:
                                tx_bad0.append(tx_hash)
                                tx_index[tx_hash] = (i1a, i2a)
                            break
                        i2b += 1
                    i1b += 1
                i2a += 1
            i1a += 1
        tx_bad = tx_bad0 #list(tx_bad0)

        # DEBUG ONLY
        # tx_bad = []
        # tx_index = {}
        # for i1 in range(len(rez_batch)):
        #     for i2 in range(len(rez_batch[i1])):
        #         tx_bad.append(rez_batch[i1][i2]['hash'])
        #         tx_index[rez_batch[i1][i2]['hash']] = (i1, i2)
        # DEBUG mode  END

        return tx_bad, tx_index

    def execute_tx_batch(self, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1):
        if len(batch['transactions'])==0:
            return []
        environment = self.generate_environment(driver, timestamp, input_hash, bhash, num)
        set_pool_executor(self.executor)

        global pool
        if len(pool) == 0:
            self.start_pool()
            log.debug(f'Initialyze pool {len(pool)}')

        i = 0
        s = time()
        log.debug(f"Start Pool len={self.active_workers}  prc={self.work_pool}")

        for transaction in batch['transactions']:
            log.debug(f'Transaction {i}   {type(self.executor)}')
            it = (transaction, stamp_cost, environment, i, None)
            i_prc = self.work_pool[i % self.active_workers]
            pool[i_prc].q_in.put(it)
            i += 1

        N_tx = i
        tx_data = self.wait_tx_result(N_tx)

        log.debug(f"End of pool. result_list={tx_data}")
        tx_done_ok = [tx['tx_number'] for tx in tx_data]
        log.debug(f"tx_data={len(tx_data)}  tx_done_ok={tx_done_ok} duration= {time() - s}")
        return tx_data

    def prepare_data(self, tx_data):
        out_data = []
        for tx in tx_data:
            tx_output = {
                'hash': tx['hash'],
                'transaction': tx['transaction'],
                'status': tx['status'],
                'state': tx['state'],
                'stamps_used': tx['stamps_used'],
                'result': tx['result'],
            }
            tx_output = format_dictionary(tx_output)
            out_data.append(tx_output)
        return out_data

    def rerun_txs(self, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1, tx_idx=None,
                  result0=None, ):

        environment = self.generate_environment(driver, timestamp, input_hash, bhash, num)
        set_pool_executor(self.executor)

        i = 0
        s = time()

        self.executor.driver.pending_writes.clear()
        tot_pwrites = set()
        for tx_hash in batch:
            i1, i2 = tx_idx[tx_hash]
            ini_pwrites = result0[i1][i2]['p_writes']
            tot_pwrites.update(ini_pwrites.keys())
        tot_pwrites = list(tot_pwrites)

        for kk in range (len(self.work_pool)):
            it = (None, None, environment, 0, tot_pwrites)
            i_prc = self.work_pool[kk]
            pool[i_prc].q_in.put(it)

        self.active_workers = 1
        for tx_hash in batch:
            i1, i2 = tx_idx[tx_hash]
            log.debug(f'i1, i2 {i1, i2} {tx_hash} ')
            transaction = result0[i1][i2]['transaction']
            log.debug(f'Transaction {i} {transaction}')
            it = (transaction, stamp_cost, environment, i, None)
            i_prc = self.work_pool[0]
            pool[i_prc].q_in.put(it)
            i += 1

        N_tx = i
        tx_data = self.wait_tx_result(N_tx)

        i = 0
        for tx_hash in batch:
            i1, i2 = tx_idx[tx_hash]
            result0[i1][i2] = tx_data[i]
            i += 1
        log.debug(f"End of rerun. result_list={result0} duration= {time() - s}")
        return result0

    def rerun_txs2(self, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1, tx_idx=None,
                  result0=None, ):

        environment = self.generate_environment(driver, timestamp, input_hash, bhash, num)
        set_pool_executor(self.executor)

        i = 0
        s = time()

        self.executor.driver.pending_writes.clear()
        tot_pwrites = set()
        for tx_hash in batch:
            i1, i2 = tx_idx[tx_hash]
            ini_pwrites = result0[i1][i2]['p_writes']
            tot_pwrites.update(ini_pwrites.keys())
        tot_pwrites = list(tot_pwrites)

        for kk in range (len(self.work_pool)):
            it = (None, None, environment, 0, tot_pwrites)
            i_prc = self.work_pool[kk]
            pool[i_prc].q_in.put(it)

        self.active_workers = 1
        for tx_hash in batch:
            i1, i2 = tx_idx[tx_hash]
            log.debug(f'i1, i2 {i1, i2} {tx_hash} ')
            transaction = result0[i1][i2]['transaction']

            log.debug(f'Transaction {i} {transaction}')
            it = (transaction, stamp_cost, environment, i, None)
            i_prc = self.work_pool[0]
            pool[i_prc].q_in.put(it)
            i += 1

        N_tx = i
        tx_data = self.wait_tx_result(N_tx)

        result_m = []
        for tx2 in result0:
            tb2 = []
            for tx in tx2:
                if tx['hash'] not in batch:
                    tb2.append(tx)
            if len(tb2) > 0:
                result_m.append(tb2)

        # for tx_hash in batch:
        #     i1, i2 = tx_idx[tx_hash]
        #     log.debug(f'delete i1, i2 {i1, i2} {tx_hash} ')
        #     log.debug(f' result0[i1][i2] = {result0[i1][i2]}')
        #     del result0[i1][i2]

        result_m.append(tx_data)
        log.debug(f"End of rerun2. result_list={result_m} duration= {time() - s}")

        return result_m

    def init_pool(self, work=None):
        # Assume single threaded, single process for now.
        global pool
        if len(pool) == 0:
            self.start_pool()
            log.debug(f'Initialyze pool {len(pool)}')
        l_max = 1
        if work is not None:
            for tx_batch in work:
                l_max = max(l_max, len(tx_batch['transactions']))

        self.work_pool, self.active_workers = self.get_pool(l_max)

    def execute_work(self, driver, work, wallet, previous_block_hash, current_height=0, stamp_cost=20000,
                     parallelism=4):

        self.init_pool(work)
        rez_batch = []
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
            rez_batch.append(results)

        tx_bad, tx_bad_idx = self.check_conflict2(rez_batch)
        log.debug(f"tx_bad={tx_bad} tx_bad_idx= {tx_bad_idx}")
        if len(tx_bad) > 0:
            rez_batch2 = self.rerun_txs2(
                driver=driver,
                batch=tx_bad,
                timestamp=work[0]['timestamp'],
                input_hash=work[0]['input_hash'],
                stamp_cost=stamp_cost,
                bhash=previous_block_hash,
                num=current_height,
                tx_idx=tx_bad_idx,
                result0=rez_batch,
            )
            log.debug(f"rez_batch2={rez_batch2}")
            rez_batch = rez_batch2
        self.free_pool(self.work_pool)

        subblocks = []
        i = 0
        for results0 in rez_batch:
            results = self.prepare_data(results0)
            tx_batch = work[i]

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
            while n_step < POOL_WAIT_STEPS:
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
        if stop_cmd is None:
            return
        stop_cmd.value = 1
        for i in range(__N_WORKER__):
            pool[i].join()
        log.info(f" Workers stopped OK")

    def wait_tx_result(self, N_tx):
        kk = 0
        k_step = 0
        k_wait = N_tx * N_TRY_PER_TX
        rez = []
        while k_step < k_wait:
            for i_tx in range(N_tx):
                try:
                    k_step += 1
                    i_prc = self.work_pool[i_tx % self.active_workers]
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
                        output = self.executor.execute_tx(tx_input[0], tx_input[1], environment= tx_input[2], tx_number=tx_input[3], ini_writes=tx_input[4])
                        if tx_input[4] is None:
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
    def __init__(self, executor):
        self.executor = executor

    def execute_tx(self, transaction, stamp_cost, environment: dict = {}):
        # Deserialize Kwargs. Kwargs should be serialized JSON moving into the future for DX.

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

    def execute_tx_batch(self, driver, batch, timestamp, input_hash, stamp_cost, bhash='0' * 64, num=1):
        environment = self.generate_environment(driver, timestamp, input_hash, bhash, num)

        # Each TX Batch is basically a subblock from this point of view and probably for the near future
        tx_data = []
        for transaction in batch['transactions']:
            tx_data.append(self.execute_tx(transaction=transaction,
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

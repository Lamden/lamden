from cilantro_ee.logger.base import get_logger
from cilantro_ee.constants.conf import CilantroConf
from cilantro_ee.messages.transaction.contract import ContractTransaction
import zmq, asyncio, sched, time, random

WORDS = ("butt", "orange", "trump", "yellow", "ketchup", "chonks", "chungus", "bigbio", "thicc n sicc")
MAX_UUID = 2 ** 32


class AsyncioScheduler:

    def __init__(self, new_loop=True):
        self.log = get_logger("AsyncioScheduler")
        self.loop = asyncio.new_event_loop() if new_loop else asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        self.sk = CilantroConf.SK or "A"*64  # this is just for testing
        self.events = {}

        self.loop.run_until_complete(asyncio.gather(self.schedule_things()))

    def send_tx(self, contract_name, fn_name, kwargs):
        print("sending {}.{} with kwargs {}".format(contract_name, fn_name, kwargs))
        # TODO send dat TX for REAL
        tx = ContractTransaction.create(sender_sk=self.sk, stamps_supplied=0, contract_name=contract_name,
                                        func_name=fn_name, nonce='', kwargs=kwargs)

    async def _run_tx(self, uuid, send_time, contract_name, fn_name, kwargs):
        curr_t = time.time()
        delay = send_time - curr_t

        if delay < 0:
            self.log.warning("attempting to schedule an event with send_time {} that is in the past".format(send_time))
            return

        try:
            await self.__run_tx(delay, contract_name, fn_name, kwargs)
        except asyncio.CancelledError():
            self.log.debugv("run_tx cancelled")
        finally:
            if uuid in self.events:
                del self.events[uuid]

    async def __run_tx(self, delay, contract_name, fn_name, kwargs):
        await asyncio.sleep(delay)
        self.send_tx(contract_name, fn_name, kwargs)

    def schedule_tx(self, time, contract_name, fn_name, kwargs):
        uuid = random.randint(0, MAX_UUID)
        fut = asyncio.ensure_future(self._run_tx(uuid, time, contract_name, fn_name, kwargs))
        self.events[uuid] = fut

    def flush_schedules(self):
        self.log.info("Flushing {} scheduled events".format(len(self.events)))
        for k in self.events:
            self.events[k].cancel()
            del self.events[k]

    async def schedule_things(self):
        for _ in range(10):
            t = random.randint(1, 10)

            print("scheduling something in {} seconds".format(t))
            self.schedule_tx(time.time() + t, 'some_contract', 'some_fn', kwargs={'that': random.choice(WORDS)})

            await asyncio.sleep(2)


if __name__ == "__main__":
    s = AsyncioScheduler()

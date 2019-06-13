from cilantro_ee.logger.base import get_logger
from cilantro_ee.constants import conf
from cilantro_ee.messages.transaction.contract import ContractTransaction
from cilantro_ee.storage.vkbook import VKBook
import asyncio, time, random, aiohttp

WORDS = ("butt", "orange", "trump", "yellow", "ketchup", "chonks", "chungus", "bigbio", "thicc n sicc")
MAX_UUID = 2 ** 32


class AsyncioScheduler:

    def __init__(self):
        self.log = get_logger("AsyncioScheduler")
        self.loop = asyncio.get_event_loop()

        self.sk = conf.SK
        self.events = {}
        self.session = aiohttp.ClientSession()

        # Set masternode IPs
        # TODO do away with this jankery and find a proper mechanism to get a set of masternode IPs
        self.mn_ips = [conf.VK_IP_MAP[vk] for vk in VKBook.get_masternodes()]

    async def send_tx(self, contract_name, fn_name, kwargs):
        print("sending {}.{} with kwargs {}".format(contract_name, fn_name, kwargs))
        tx = ContractTransaction.create(sender_sk=self.sk, stamps_supplied=0, contract_name=contract_name,
                                        func_name=fn_name, nonce='', kwargs=kwargs)

        # TODO refactor this masternode url generation business into an appropriate module (maybe network topology?)
        if conf.SSL_ENABLED:
            mn_url = "https://{}:80".format(random.choice(self.mn_ips))
        else:
            mn_url = "http://{}:8080".format(random.choice(self.mn_ips))

        # TODO get some feedback on if this TX was sent successfully or not??
        async with self.session.post(mn_url, data=tx.serialize()) as resp:
            return await resp.json()

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
        await self.send_tx(contract_name, fn_name, kwargs)

    def schedule_tx(self, uuid, time, contract_name, fn_name, kwargs):
        uuid = uuid or random.randint(0, MAX_UUID)
        fut = asyncio.ensure_future(self._run_tx(uuid, time, contract_name, fn_name, kwargs))
        self.events[uuid] = fut

    def flush_schedules(self):
        self.log.info("Flushing {} scheduled events".format(len(self.events)))
        for k in self.events:
            self.events[k].cancel()
            del self.events[k]

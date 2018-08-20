from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.messages.base.base_json import MessageBaseJson
from cilantro.protocol.states.decorators import *
import time, random, asyncio
from cilantro.utils.lprocess import LProcess
from cilantro.protocol import wallet as W


PORT = 1234
LOCAL_HOST = '127.0.0.1'
FILTER = 'trumpisaracistconvincemeotherwise'

PROD_SK = W.new()[0]
CONSUMER1_SK = W.new()[0]
CONSUMER2_SK = W.new()[0]


class Poke(MessageBaseJson):
    def validate(self):
        pass

    @classmethod
    def create(cls, msg: str):
        return cls.from_data({'msg': msg})

    @property
    def message(self):
        return self._data['msg']


class Producer(Worker):
    def setup(self):
        self.composer.add_pub(protocol='ipc', port=PORT, ip=LOCAL_HOST)
        self.num_pokes = 36
        self.poke_rest = 1
        self.poke_msgs = ['hi', 'sup', 'yo', 'ay', 'whats good', 'hello', 'hey', 'herro']
        asyncio.ensure_future(self.start_poking())

    async def start_poking(self):
        while self.num_pokes > 0:
            self.num_pokes -= 1
            msg = random.choice(self.poke_msgs)
            poke = Poke.create(msg)
            self.log.notice("Sending poke with msg {}".format(msg))
            self.composer.send_pub_msg(filter=FILTER, message=poke)
            await asyncio.sleep(self.poke_rest)

        self.log.important("Producer done poking!")


class Consumer(Worker):
    def setup(self):
        self.composer.add_sub(filter=FILTER, protocol='ipc', port=PORT, ip=LOCAL_HOST)

    @input(Poke)
    def handle_poke(self, poke: Poke):
        self.log.notice("Consumer poked with message {}".format(poke.message))


if __name__== "__main__":
    producer = LProcess(target=Producer, kwargs={'name': 'Producer'})
    consumer1 = LProcess(target=Consumer, kwargs={'name': 'Consumer_1'})

    for p in (producer, consumer1):
        p.start()

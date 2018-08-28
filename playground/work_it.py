from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.messages.base.base_json import MessageBaseJson
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.states.decorators import *
import time, random, asyncio
from cilantro.utils.lprocess import LProcess
from cilantro.protocol import wallet as W


PUBSUB_PORT = 1234
DEALROUTE_PORT = 4321
LOCAL_HOST = '127.0.0.1'
FILTER = 'trumpisaracistconvincemeotherwise'

PROD_SK = W.new()[0]
CONSUMER1_SK = W.new()[0]
CONSUMER2_SK = W.new()[0]

POKE_MSGS = ['hi', 'sup', 'yo', 'ay', 'whats good', 'hello', 'hey', 'herro', 'sup fam']

Q_AND_A = {
    'do you like fat cats or skinny cats': 'fat cats pls or no cats at all',
    'what is the purpose of dreaming at night': 'to defragment your hard drive irl',
    'damn y r u still up davis': 'cause i gotta spit this hot code'
}


class Poke(MessageBaseJson):
    def validate(self):
        pass

    @classmethod
    def create(cls, msg: str):
        return cls.from_data({'msg': msg})

    @property
    def message(self):
        return self._data['msg']


class QuestionRequest(MessageBaseJson):
    def validate(self):
        pass

    @classmethod
    def create(cls, question: str):
        return cls.from_data({'question': question})

    @property
    def question(self):
        return self._data['question']


class AnswerReply(MessageBaseJson):
    def validate(self):
        pass

    @classmethod
    def create(cls, answer: str):
        return cls.from_data({'answer': answer})

    @property
    def answer(self):
        return self._data['answer']


class Producer(Worker):
    def setup(self):
        self.composer.add_pub(protocol='ipc', port=self.pubsub_port, ip=self.ip)
        self.composer.add_router(protocol='ipc', port=self.dealroute_port, ip=self.ip)
        asyncio.ensure_future(self.start_poking())

    @input_socket_connected
    def socket_connected(self, *args, **kwargs):
        self.log.notice("Socket connected called with args {} and kwargs {}".format(args, kwargs))

    async def start_poking(self):
        while self.num_pokes > 0:
            self.num_pokes -= 1
            msg = random.choice(POKE_MSGS)
            poke = Poke.create(msg)
            self.log.info("Sending poke with msg {}".format(msg))
            self.composer.send_pub_msg(protocol='ipc', port=self.pubsub_port, filter=self.filter, message=poke)
            await asyncio.sleep(self.rest_time)

        self.log.important("Producer done poking!")

    @input_request(QuestionRequest)
    def handle_question(self, question: QuestionRequest, **kwargs):
        q = question.question
        self.log.info("Producer got question {}".format(q))
        reply = AnswerReply.create(Q_AND_A[q])
        return reply


class PubSubConsumer(Worker):
    def setup(self):
        self.composer.add_sub(filter=self.filter, protocol='ipc', port=self.pubsub_port, ip=self.ip)

    @input_socket_connected
    def socket_connected(self, *args, **kwargs):
        self.log.notice("Socket connected called with args {} and kwargs {}".format(args, kwargs))

    @input(Poke)
    def handle_poke(self, poke: Poke):
        self.log.important("PubSubConsumer poked with message {}".format(poke.message))


class RepReplyConsumer(Worker):
    def setup(self):
        self.composer.add_dealer(protocol='ipc', port=self.dealroute_port, ip=self.ip)
        asyncio.ensure_future(self.start_asking())

    @input_socket_connected
    def socket_connected(self, *args, **kwargs):
        self.log.notice("Socket connected called with args {} and kwargs {}".format(args, kwargs))

    async def start_asking(self):
        while self.num_questions > 0:
            self.num_questions -= 1
            q = random.choice(list(Q_AND_A.keys()))
            self.log.info("Asking question {}".format(q))

            msg = QuestionRequest.create(q)
            self.composer.send_request_msg(message=msg, protocol='ipc', port=self.dealroute_port, ip=self.ip)

            await asyncio.sleep(self.rest_time)

    @input(AnswerReply)
    def handle_answer(self, answer: AnswerReply, envelope: Envelope, **kwargs):
        self.log.important2("Got answer {} ".format(answer.answer))


if __name__== "__main__":
    # All these kwargs get set as instance variables on the Producer instance. So, for example,
    # inside producer code, self.num_pokes = 36, self.rest_time = 3, ect ect
    producer = LProcess(target=Producer, kwargs={'name': 'Sir Producer', 'num_pokes': 36, 'rest_time': 3,
                                                 'pubsub_port': PUBSUB_PORT, 'dealroute_port': DEALROUTE_PORT,
                                                 'ip': LOCAL_HOST, 'filter': FILTER, 'signing_key': PROD_SK})

    pubsub_consumer = LProcess(target=PubSubConsumer, kwargs={'name': 'Mr. PubSubConsumer', 'pubsub_port': PUBSUB_PORT, 'ip': LOCAL_HOST,
                                                        'filter': FILTER, 'signing_key': CONSUMER1_SK})
    dealroute_consumer = LProcess(target=RepReplyConsumer,
                                  kwargs={'name': 'Ms. ReqReplyConsumer', 'dealroute_port': DEALROUTE_PORT,
                                          'ip': LOCAL_HOST, 'rest_time': 2, 'num_questions': 42, 'signing_key': CONSUMER2_SK})

    for p in (producer, pubsub_consumer, dealroute_consumer):
        p.start()

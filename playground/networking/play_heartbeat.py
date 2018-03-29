from cilantro.networking import BaseNode
import time
from cilantro.networking import Delegate
from cilantro.serialization import JSONSerializer


def beat():
    return b'hh'


CONSENSUS_TIME = 1


class Heartbeat(BaseNode):
    def __init__(self, host='127.0.0.1', sub_port='8888', serializer=JSONSerializer, pub_port='7878'):
        BaseNode.__init__(self, host=host, sub_port=sub_port, pub_port=pub_port, serializer=serializer)
        #self.filters = [b'h']
        self.is_beating = False

    def handle_req(self, data: bytes):
        print(data)
        if data == b'hh':
            print('starting heart.')
            self.start_heart()

    async def start_heart(self):
        while True:
            print('ba bump...')
            self.publish_req(beat())
            time.sleep(CONSENSUS_TIME)


h = Heartbeat()
h.start_async()

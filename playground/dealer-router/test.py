from cilantro.protocol.reactor import ReactorInterface
from cilantro.logger import get_logger
import time

URL = 'tcp://127.0.0.1:3530'


class Requester:
    _ID = 'ASS'
    def __init__(self):
        self.reactor = ReactorInterface(self)
        self.log = get_logger("Requester")
        self.reactor.add_dealer(url=URL, callback='handle_reply', id=self._ID)
        self.reactor.notify_ready()

    def handle_reply(self, rep):
        self.log.critical("Got reply: {}".format(rep))

    def send_req(self, req_str):
        self.reactor.request(url=URL, data=req_str.encode())


class Replier:
    def __init__(self):
        self.reactor = ReactorInterface(self)
        self.log = get_logger("Replier")
        self.reactor.add_router(url=URL, callback='handle_request')
        self.reactor.notify_ready()

    def handle_request(self, req, id):
        self.log.critical("Got request: {} with sender id: {}".format(req, id))
        self.reactor.reply(url=URL, id=id, data=b'heres your reply my guy')


if __name__ == "__main__":
    requester = Requester()
    replier = Replier()

    time.sleep(1)

    requester.send_req("racks on racks on racks")

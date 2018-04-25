from cilantro.protocol.reactor import ReactorInterface
from cilantro.logger import get_logger
import time


URL = "tcp://127.0.0.1:5566"
URL2 = "tcp://127.0.0.1:5577"
URL3 = "tcp://127.0.0.1:5588"
URL4 = "tcp://127.0.0.1:5599"


class Node:
    def __init__(self, log_color=None):
        if log_color:
            self.log = get_logger("Node", bg_color=log_color)
        else:
            self.log = get_logger("Node")

        self.log.info("A Node has appeared")
        self.reactor = ReactorInterface(router=self)
        self.reactor.notify_ready()

    def handle_msg(self, data):
        self.log.info("Handling Msg: {}".format(data))

if __name__ == "__main__":
    log = get_logger("Main", bg_color='red')
    log.debug("Main")

    sub = Node(log_color='magenta')
    sub.reactor.add_sub(url=URL, callback='handle_msg')

    pub = Node(log_color='blue')
    pub.reactor.add_pub(url=URL)

    time.sleep(0.5)
    pub.reactor.pub(url=URL, data=b'hello guy')

from cilantro_ee.storage.ledis import SafeLedis
from cilantro_ee.storage.state import StateDriver
from cilantro_ee.nodes.state_sync import IPC_ROUTER_IP, IPC_ROUTER_PORT, IPC_PUB_IP, IPC_PUB_PORT
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int
import zmq, asyncio


class TaskSender(Worker):

    def __init__(self, ip, *args, task_idx=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("TaskSender")
        self.task_idx = task_idx
        self.dealer, self.sub = None, None
        self.run()

    def run(self):
        self.build_task_list()
        self.log.info("TaskSender starting event loop...")
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.dealer = self.manager.create_socket(socket_type=zmq.DEALER, secure=False, name="TaskSender-IPC-Dealer")
        self.dealer.setsockopt(zmq.IDENTITY, str(self.task_idx).encode())
        self.dealer.connect(port=IPC_ROUTER_PORT, protocol="ipc", ip=IPC_ROUTER_IP)
        self.tasks.append(self.dealer.add_handler(self.handle_dealer_msg))

        self.sub = self.manager.create_socket(socket_type=zmq.SUB, secure=False, name="TaskSender-IPC-Dealer")
        self.sub.setsockopt(zmq.SUBSCRIBE, STATESYNC_FILTER.encode())
        self.sub.connect(port=IPC_PUB_PORT, protocol="ipc", ip=IPC_PUB_IP)
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))

    def handle_dealer_msg(self, frames):
        self.log.important("IPC DEALER got frames {}".format(frames))

    def handle_sub_msg(self, frames):
        self.log.important("IPC SUB got frames {}".format(frames))

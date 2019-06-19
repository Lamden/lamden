from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.signals.state_sync import *
from cilantro_ee.storage.driver import SafeDriver
from cilantro_ee.nodes.state_sync import IPC_ROUTER_IP, IPC_ROUTER_PORT, IPC_PUB_IP, IPC_PUB_PORT
from cilantro_ee.nodes.scheduler.asyncio_scheduler import AsyncioScheduler
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int
import zmq, asyncio


MOCK_DATA = {'0':
                 {'time': 900000000,
                  'contract_name':'currency',
                  'fn_name':'balance_of',
                  'kwargs':
                      {'wallet_id': 'davis'}
                  }
             }


class TaskSender(Worker):

    def __init__(self, ip, *args, task_idx=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("TaskSender")
        self.task_idx = task_idx
        self.dealer, self.sub = None, None
        self.sched = AsyncioScheduler()
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
        self.log.spam("IPC SUB got frames {}".format(frames))

        msg_type = bytes_to_int(frames[1])
        msg_blob = frames[2]
        msg = MessageBase.registry[msg_type].from_bytes(msg_blob)

        if isinstance(msg, UpdatedStateSignal):
            self.log.info("Got update state signal. Refreshing schedules")
            self._update_schedules()

    def _update_schedules(self):
        # TODO optimize this....this brute force schedules ALL events every new block LOL

        self.sched.flush_schedules()
        # TODO get this data for real from the DB...
        for sched_id in MOCK_DATA:
            data = MOCK_DATA[sched_id]
            self.sched.schedule_tx(sched_id, time=data['time'], contract_name=data['contract_name'],
                                   fn_name=data['fn_name'], kwargs=data['kwargs'])

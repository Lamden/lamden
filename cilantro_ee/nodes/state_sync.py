from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.multiprocessing.worker import Worker

from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int

from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.storage.ledis import SafeLedis
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.storage.state import StateDriver

from cilantro_ee.nodes.catchup import CatchupManager
from cilantro_ee.nodes.base import NodeBase

from cilantro_ee.constants.conf import CilantroConf
from cilantro_ee.constants.ports import *
from cilantro_ee.constants.zmq_filters import *

from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.messages.block_data.block_metadata import NewBlockNotification, SkipBlockNotification, BlockMetaData
from cilantro_ee.messages.block_data.state_update import *

import asyncio, zmq


IPC_ROUTER_IP = 'state-sync-router-ipc-sock'
IPC_ROUTER_PORT = 6174

IPC_PUB_IP = 'state-sync-pub-ipc-sock'
IPC_PUB_PORT = 6175


class StateSyncNode(NodeBase):
    def start_node(self):
        self.log.info("Starting StateSync processes")
        self.sync = LProcess(target=StateSync, name='StateSync',
                             kwargs={'signing_key': self.signing_key, 'ip': self.ip})
        self.sync.start()


class StateSync(Worker):
    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("StateSync")
        self.ip = ip

        # these guys get set in build_task_list
        self.router, self.sub, self.pub, self.ipc_router, self.ipc_pub = None, None, None, None, None
        self.catchup = None

        self.run()

    def run(self):
        self.build_task_list()
        self.log.info("StateSync starting event loop")
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.router = self.manager.create_socket(
            socket_type=zmq.ROUTER,
            name="StateSync-Router-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        # self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
        self.router.bind(port=SS_ROUTER_PORT, protocol='tcp', ip=self.ip)
        self.tasks.append(self.router.add_handler(self.handle_router_msg))

        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-IPC-Router")
        self.ipc_router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.ipc_router.bind(port=IPC_ROUTER_PORT, protocol='ipc', ip=IPC_ROUTER_IP)
        self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg))

        self.ipc_pub = self.manager.create_socket(socket_type=zmq.PUB, name="StateSync-IPC-Pub", secure=False)
        self.ipc_pub.bind(port=IPC_PUB_PORT, protocol="ipc", ip=IPC_PUB_IP)

        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="StateSync-Pub-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        self.pub.bind(port=SS_PUB_PORT, protocol='tcp', ip=self.ip)

        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="StateSync-Sub-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))

        self.tasks.append(self._connect_and_process())

        self.catchup = CatchupManager(verifying_key=self.verifying_key, pub_socket=self.pub, router_socket=self.router,
                                      store_full_blocks=False)

    async def catchup_db_state(self):
        await asyncio.sleep(6)  # so pub/sub connections can complete
        assert self.catchup, "Expected catchup_mgr initialized at this point, learn to fking code pls"

        self.log.info("Catching up...")
        self.catchup.run_catchup()

    async def _connect_and_process(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()

        # Listen to Masternodes over sub and connect router for catchup communication
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_masternodes():
            self.sub.connect(vk=vk, port=MN_PUB_PORT)
            self.dealer.connect(vk=vk, port=MN_ROUTER_PORT)

        # now start the catchup
        await self.catchup_db_state()

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        msg_hash = envelope.message_hash

        if isinstance(msg, NewBlockNotification):
            self.log.info("Got NewBlockNotification from sender {} with hash {}".format(envelope.sender, msg.block_hash))
            # TODO send this to catchup manager
        else:
            self.log.warning("Got unexpected message type {}".format(type(msg)))

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        sender = envelope.sender
        assert sender.encode() == frames[0], "Sender vk {} does not match id frame {}".format(sender.encode(),
                                                                                              frames[0])
        msg = envelope.message

        if isinstance(msg, BlockIndexReply):
            self.log.important("Got BlockIndexReply {}".format(msg))
            # TODO handle this (pass to catchup manager)
            # self.recv_block_idx_reply(sender, msg)
            pass
        elif isinstance(msg, BlockDataReply):
            self.log.important("Got BlockDataReply {}".format(msg))
            # TODO handle this (pass to catchup manager)
            # self.recv_block_data_reply(msg)
            pass
        else:
            raise Exception("Got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def handle_ipc_msg(self, frames):
        self.log.spam("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this
        assert len(frames) == 3, "Expected 3 frames: (id, msg_type, msg_blob). Got {} instead.".format(frames)

        # TODO logic here

    def _send_msg_over_ipc_pub(self, message: MessageBase):
        self.log.debug("Publishing message {} over IPC".format(message))
        message_type = MessageBase.registry[type(message)]
        self.ipc_pub.send_multipart([STATESYNC_FILTER.encode(), int_to_bytes(message_type), message.serialize()])

    def _send_msg_over_ipc_router(self, task_idx: int, message: MessageBase):
        """ Convenience method to send a MessageBase instance over IPC router socket to a particular dealer.
         Includes a frame to identify the type of message """
        self.log.spam("Sending msg to task_idx {} with payload {}".format(task_idx, message))
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        id_frame = str(task_idx).encode()
        message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
        self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])

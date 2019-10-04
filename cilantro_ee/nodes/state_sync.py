# from cilantro_ee.core.logger.base import get_logger
# from cilantro_ee.core.utils.worker import Worker
#
# from cilantro_ee.utils.lprocess import LProcess
#
# from cilantro_ee.services.storage.vkbook import PhoneBook
#
# from cilantro_ee.nodes.catchup import CatchupManager
# from cilantro_ee.nodes.base import NodeBase
#
# from cilantro_ee.constants.ports import *
# from cilantro_ee.constants.zmq_filters import *
#
# from cilantro_ee.messages.envelope.envelope import Envelope
# from cilantro_ee.messages.block_data.notification import NewBlockNotification
# from cilantro_ee.messages.block_data.state_update import *
# from cilantro_ee.messages.signals.state_sync import UpdatedStateSignal
#
# import asyncio, zmq, math
# from collections import defaultdict
#
#
# IPC_ROUTER_IP = 'state-sync-router-ipc-sock'
# IPC_ROUTER_PORT = 6174
#
# IPC_PUB_IP = 'state-sync-pub-ipc-sock'
# IPC_PUB_PORT = 6175
#
#
# class StateSyncNode(NodeBase):
#     def start_node(self):
#         self.log.info("Starting StateSync processes")
#         self.sync = LProcess(target=StateSync, name='StateSync',
#                              kwargs={'signing_key': self.signing_key, 'ip': self.ip})
#         self.sync.start()
#
#
# class StateSync(Worker):
#     def __init__(self, ip, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.log = get_logger("StateSync")
#         self.ip = ip
#
#         # these guys get set in build_task_list
#         self.router, self.sub, self.pub, self.ipc_router, self.ipc_pub = None, None, None, None, None
#         self.cm = None
#
#         self.is_caught_up = False
#         self.new_blk_notifs = defaultdict(list)  # mapping of block hash to new_block_notif messages
#         self.mn_quorum = PhoneBook.masternode_quorum_min
#
#         self.run()
#
#     def run(self):
#         self.build_task_list()
#         self.log.info("StateSync starting event loop")
#         self.loop.run_until_complete(asyncio.gather(*self.tasks))
#
#     def build_task_list(self):
#         self.router = self.manager.create_socket(
#             socket_type=zmq.ROUTER,
#             name="StateSync-Router-{}".format(self.verifying_key[-4:]),
#             secure=True,
#         )
#         # self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
#         self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
#         self.router.bind(port=SS_ROUTER_PORT, protocol='tcp', ip=self.ip)
#         self.tasks.append(self.router.add_handler(self.handle_router_msg))
#
#         self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-IPC-Router")
#         self.ipc_router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
#         self.ipc_router.bind(port=IPC_ROUTER_PORT, protocol='ipc', ip=IPC_ROUTER_IP)
#         self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg))
#
#         self.ipc_pub = self.manager.create_socket(socket_type=zmq.PUB, name="StateSync-IPC-Pub", secure=False)
#         self.ipc_pub.bind(port=IPC_PUB_PORT, protocol="ipc", ip=IPC_PUB_IP)
#
#         self.pub = self.manager.create_socket(
#             socket_type=zmq.PUB,
#             name="StateSync-Pub-{}".format(self.verifying_key[-4:]),
#             secure=True,
#         )
#         self.pub.bind(port=SS_PUB_PORT, protocol='tcp', ip=self.ip)
#
#         self.sub = self.manager.create_socket(
#             socket_type=zmq.SUB,
#             name="StateSync-Sub-{}".format(self.verifying_key[-4:]),
#             secure=True,
#         )
#         self.sub.setsockopt(zmq.SUBSCRIBE, NEW_BLK_NOTIF_FILTER.encode())
#         self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
#
#         self.tasks.append(self._connect_and_process())
#
#         self.cm = CatchupManager(verifying_key=self.verifying_key, signing_key=self.signing_key, pub_socket=self.pub, router_socket=self.router,
#                                  store_full_blocks=False)
#
#     async def catchup_db_state(self):
#         await asyncio.sleep(6)  # so pub/sub connections can complete
#         assert self.cm, "Expected catchup_mgr initialized at this point, learn to fking code pls"
#
#         self.log.info("Catching up...")
#         self.cm.run_catchup()
#
#     def check_catchup(self, caught_up: bool):
#         if not caught_up:
#             self.log.important("Setting caught up to false")
#             self.is_caught_up = caught_up
#
#         elif not self.is_caught_up and caught_up:
#             self.log.important("Setting caught up to true, and running caughtup behavior")
#             self.is_caught_up = True
#             self.new_blk_notifs.clear()
#             self.run_caughtup_behavior()
#
#     def run_caughtup_behavior(self):
#         self._send_msg_over_ipc_pub(UpdatedStateSignal.create())
#
#     async def _connect_and_process(self):
#         # first make sure, we have overlay server ready
#         await self._wait_until_ready()
#
#         # Listen to Masternodes over sub and connect router for cm communication
#         for vk in PhoneBook.masternodes:
#             self.sub.connect(vk=vk, port=MN_PUB_PORT)
#             self.router.connect(vk=vk, port=MN_ROUTER_PORT)
#
#         # now start the cm
#         await self.catchup_db_state()
#
#     def handle_sub_msg(self, frames):
#         # Unpack the frames
#         msg_filter, msg_type, msg_blob = frames
#
#         # TODO -- consensus on NewBlockNotifications before we feed it to the cm manager
#
#         if msg_type == MessageTypes.BLOCK_NOTIFICATION:
#             # Unpack the message
#             external_message = signal_capnp.ExternalMessage.from_bytes_packed(msg_blob)
#
#             # If the sender has signed the payload, continue
#             if not _verify(external_message.sender, external_message.data, external_message.signature):
#                 return
#
#             # Unpack the block
#             block = BlockNotification.unpack_block_notification(external_message.data)
#             if block.type.which() == "newBlock":
#                 self.log.info("Got NewBlockNotification from sender {} with hash {}".format(external_message.sender, block.blockHash.hex()))
#                 self._handle_new_blk_notif(block)
#         else:
#             self.log.warning("Got unexpected message type {}".format(type(msg)))
#
#     def _handle_new_blk_notif(self, nbc: notification_capnp.BlockNotification):
#         self.new_blk_notifs[nbc.block_hash].append(nbc)
#         if len(self.new_blk_notifs[nbc.block_hash]) >= self.mn_quorum:
#             del self.new_blk_notifs[nbc.block_hash]
#             self.log.important3("Sending NBC {} to catchup manager".format(nbc))  # TODO delete
#             self.check_catchup(self.cm.recv_new_blk_notif(nbc))
#
#     def handle_router_msg(self, frames):
#         envelope = Envelope.from_bytes(frames[-1])
#         sender = envelope.sender
#         assert sender.encode() == frames[0], "Sender vk {} does not match id frame {}".format(sender.encode(),
#                                                                                               frames[0])
#         msg = envelope.message
#
#         if isinstance(msg, BlockIndexReply):
#             self.log.debugv("Got BlockIndexReply {}".format(msg))
#             self.check_catchup(self.cm.recv_block_idx_reply(sender, msg))
#
#         elif isinstance(msg, BlockDataReply):
#             self.log.debugv("Got BlockDataReply {}".format(msg))
#             self.check_catchup(self.cm.recv_block_data_reply(msg))
#
#         else:
#             raise Exception("Got message type {} from ROUTER socket that it does not know how to handle"
#                             .format(type(msg)))
#
#     def handle_ipc_msg(self, frames):
#         self.log.spam("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this
#         assert len(frames) == 3, "Expected 3 frames: (id, msg_type, msg_blob). Got {} instead.".format(frames)
#
#         # TODO logic here
#
#     def _send_msg_over_ipc_pub(self, message: MessageBase):
#         self.log.debug("Publishing message {} over IPC".format(message))
#         message_type = MessageBase.registry[type(message)]
#         self.ipc_pub.send_multipart([STATESYNC_FILTER.encode(), message_type, message.serialize()])
#
#     def _send_msg_over_ipc_router(self, task_idx: int, message: MessageBase):
#         """ Convenience method to send a MessageBase instance over IPC router socket to a particular dealer.
#          Includes a frame to identify the type of message """
#         self.log.spam("Sending msg to task_idx {} with payload {}".format(task_idx, message))
#         assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
#         id_frame = str(task_idx).encode()
#         message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
#         self.ipc_router.send_multipart([id_frame, message_type, message.serialize()])

# # Create a TCP Router socket for comm with other nodes
# # self.router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-Router", secure=True)
# self.router = self.manager.create_socket(
#     socket_type=zmq.ROUTER,
#     name="BM-Router-{}".format(self.verifying_key[-4:]),
#     secure=True,
# )
# # self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
# self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
# self.router.bind(port=DELEGATE_ROUTER_PORT, protocol='tcp', ip=self.ip)
# self.tasks.append(self.router.add_handler(self.handle_router_msg))
#
#
# # Create SUB socket to
# # 1) listen for subblock contenders from other delegates
# # 2) listen for NewBlockNotifications from masternodes
# self.sub = self.manager.create_socket(
#     socket_type=zmq.SUB,
#     name="BM-Sub-{}".format(self.verifying_key[-4:]),
#     secure=True,
# )
# self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
# self.sub.setsockopt(zmq.SUBSCRIBE, NEW_BLK_NOTIF_FILTER.encode())
#
# self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
# self.tasks.append(self._connect_and_process())

# Subscribe to BlockManager IPC

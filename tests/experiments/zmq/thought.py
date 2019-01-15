"""
SocketManager
- A Worker class holds exactly one SocketManager
- holds instance of overlay client


LSocket
- A wrapper around a ZMQ socket, with special functionality, including...
- Sockets will auto reconn when a NODE_ONLINE msg is received. When to rebind tho? Should we be janky and just
  wrap the bind calls in a try/except? Perhaps we shall until we can reason a better solution...
- SPECIAL PUB BEHAVIOR
    - Sockets will defer PUB sockets defer sends until BIND is complete
- SPECIAL ROUTER BEHAVIOR
    - Router sockets should wait for an ACK before they send their data (we will have a specified timeout from when last
      ACK was received, or msg from that client, if we have not recvd a msg from client or ACK is expired we rerequest
      dat ACK)


Base LSocket class has READY always True. 
"""
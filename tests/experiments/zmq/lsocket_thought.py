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

REGARDING NODE_ONLINE event
SocketManager always needs to forward NODE_ONLINE calls to LSocket for handling

LSocket
- LSocket will keep a track of which IP's it has bound/connected to for reconn behavior
- For all sockets, will try to reconnect (via bind/connect. Maybe just wrap bind in try/catch?)
- If PUB:
    - It will use this information to 'flush' send commands
- If ROUTER:
    - Mark socket as not ready. If send an ACK to the connected IP.
"""


import zmq, asyncio, zmq.asyncio
from multiprocessing import Process
import time
from cilantro.logger.base import get_logger

# /////////////////////////
# TESTING BIND IN TRY/CATCH
#
# TLDR; its ratchet but it works
# /////////////////////////


def pub(ip_to_bind):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()
    log = get_logger("PUB")

    pub = ctx.socket(zmq.PUB)
    pub.bind(ip_to_bind)

    async def start_send():
        log.info("Starting pub...")
        for i in range(100):
            log.important("Sending message {}".format(i))
            pub.send_multipart([b'', 'hi {}'.format(i).encode()])
            await asyncio.sleep(1)

            if i % 4 == 0:
                log.important3("bout 2 do a rebind for no reason")
                try:
                    pub.bind(ip_to_bind)
                except Exception as e:
                    log.notice("oh crap got error {}".format(e))

    loop.run_until_complete(start_send())


def sub(ip_to_conn):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()
    log = get_logger("SUB")

    sub = ctx.socket(zmq.SUB)
    sub.connect(ip_to_conn)
    sub.setsockopt(zmq.SUBSCRIBE, b'')

    async def start_recv():
        while True:
            log.spam("waiting for msg..")
            msg = await sub.recv_multipart()
            log.important2("Got msg {}".format(msg))

    loop.run_until_complete(start_recv())


if __name__ == '__main__':
    ip = 'tcp://127.0.0.1:8080'
    p1 = Process(target=sub, args=(ip,))
    p2 = Process(target=pub, args=(ip,))
    procs = (p1, p2)

    for p in procs:
        p.start()

    for p in procs:
        p.join()

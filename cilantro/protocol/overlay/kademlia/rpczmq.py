import asyncio
import zmq, zmq.asyncio
import logging
import os
from base64 import b64encode
from hashlib import sha1
import umsgpack
from cilantro.constants.ports import DHT_PORT
from cilantro.logger.base import get_logger
log = get_logger(__name__)

class MalformedMessage(Exception):
    """
    Message does not contain what is expected.
    """

class RPCProtocol:
    def __init__(self, loop=None, ctx=None, waitTimeout=5):
        """
        @param waitTimeout: Consider it a connetion failure if no response
        within this time window.
        """
        self._waitTimeout = waitTimeout
        self._outstanding = {}
        self.loop = loop or asyncio.get_event_loop()
        self.ctx = ctx or zmq.asyncio.Context()

    async def listen(self):
        """
        Start listening on the given port.

        Provide interface="::" to accept ipv6 address
        """
        self.identity = '{}:{}:{}'.format(self.sourceNode.ip, self.sourceNode.port, self.sourceNode.vk).encode()
        self.sock = self.ctx.socket(zmq.ROUTER)
        self.sock.setsockopt(zmq.IDENTITY, self.identity)
        self.sock.bind('tcp://*:{}'.format(self.sourceNode.port))
        log.info("Node %i listening on %s:%i",
                 self.sourceNode.long_id, '0.0.0.0', self.sourceNode.port)
        while True:
            request = await self.sock.recv_multipart()
            addr = request[0].decode().split(':')
            data = request[1]
            await self.datagram_received(data, addr)

    async def send_msg(self, addr, msgID, msg):
        sock = self.ctx.socket(zmq.DEALER)
        sock.setsockopt(zmq.IDENTITY, self.identity)
        sock.connect('tcp://{}:{}'.format(addr[0], addr[1]))
        log.spam("sending request %s for msg id %s to %s",
                  msg, b64encode(msgID), addr)
        sock.send_multipart([msg])
        response = await sock.recv_multipart()
        data = response[0]
        res = await self.datagram_received(data, addr)
        sock.close()
        return res

    async def datagram_received(self, data, addr):
        log.spam("received datagram from %s", addr)
        return await self._solveDatagram(data, addr)

    async def _solveDatagram(self, datagram, address):
        if len(datagram) < 22:
            log.warning("received datagram too small from %s,"
                        " ignoring", address)
            return

        msgID = datagram[1:21]
        data = umsgpack.unpackb(datagram[21:])

        if datagram[:1] == b'\x00':
            # schedule accepting request and returning the result
            await self._acceptRequest(msgID, data, address)
        elif datagram[:1] == b'\x01':
            return self._acceptResponse(msgID, data, address)
        else:
            # otherwise, don't know the format, don't do anything
            log.spam("Received unknown message from %s, ignoring", address)

    def _acceptResponse(self, msgID, data, address):
        msgargs = (b64encode(msgID), address)
        log.spam("received response %s for message "
                  "id %s from %s", data, *msgargs)
        return data

    async def _acceptRequest(self, msgID, data, address):
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)
        funcname, args = data
        f = getattr(self, "rpc_%s" % funcname, None)
        if f is None or not callable(f):
            msgargs = (self.__class__.__name__, funcname)
            log.warning("%s has no callable method "
                        "rpc_%s; ignoring request", *msgargs)
            return

        if not asyncio.iscoroutinefunction(f):
            f = asyncio.coroutine(f)
        response = await f(address, *args)
        log.spam("sending response %s for msg id %s to %s",
                  response, b64encode(msgID), address)
        txdata = b'\x01' + msgID + umsgpack.packb(response)
        identity = '{}:{}:{}'.format(address[0], address[1], address[2]).encode()
        self.sock.send_multipart([identity, txdata])

    def _timeout(self, msgID):
        args = (b64encode(msgID), self._waitTimeout)
        log.warning("Did not received reply for msg "
                  "id %s within %i seconds", *args)
        self._outstanding[msgID][0].set_result((False, None))
        del self._outstanding[msgID]

    def __getattr__(self, name):
        """
        If name begins with "_" or "rpc_", returns the value of
        the attribute in question as normal.
        Otherwise, returns the value as normal *if* the attribute
        exists, but does *not* raise AttributeError if it doesn't.
        Instead, returns a closure, func, which takes an argument
        "address" and additional arbitrary args (but not kwargs).
        func attempts to call a remote method "rpc_{name}",
        passing those args, on a node reachable at address.
        """
        if name.startswith("_") or name.startswith("rpc_"):
            return getattr(super(), name)

        try:
            return getattr(super(), name)
        except AttributeError:
            pass

        async def func(address, *args):
            msgID = sha1(os.urandom(32)).digest()
            data = umsgpack.packb([name, args])
            if len(data) > 8192:
                raise MalformedMessage("Total length of function "
                                       "name and arguments cannot exceed 8K")
            txdata = b'\x00' + msgID + data
            log.spam("calling remote function %s on %s (msgid %s)",
                      name, address, b64encode(msgID))

            try:
                result = await self.send_msg(address, msgID, txdata)
                return (True, result)
            except asyncio.TimeoutError:
                self._timeout(msgID)
                return (False, None)

        return func

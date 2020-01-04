import os, shutil
from os.path import join, exists
import zmq, zmq.asyncio
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator

# dir structure reset is a singleton  per node ?  node base
# dir structure create is a singleton  per process ?  worker
# what about loop ?    per process ?  worker
# Sock auth? per process ? worker


class SocketUtil:

    is_setup = False

    @classmethod
    def setup(cls, keyname):
        if not cls.is_setup:
            cls.base_dir = 'certs/{}'.format(os.getenv('HOST_NAME', keyname))
            cls.default_domain_dir = 'authorized_keys'
            cls.domain_register = set()
            cls.authorized_keys_dir = join(cls.base_dir, cls.default_domain_dir)
            cls.is_setup = True

    # this is really needed to be called only once per machine,
    # otherwise we need a inter-process locks to enforce sequentiality of this operation.
    # It is kinda enforced through sw architecture to have only one process call this
    @classmethod
    def clear_domain_register(cls):
        if exists(cls.base_dir):
            shutil.rmtree(cls.base_dir, ignore_errors=True)
        cls.domain_register.clear()

    @classmethod
    def is_domain_registered(cls, domain='*'):
        key = cls.default_domain_dir if domain == '*' else domain
        return key in cls.domain_register

    @classmethod
    def register_domain(cls, domain='*'):
        key = cls.default_domain_dir if domain == '*' else domain
        cls.domain_register.add(key)

    @classmethod
    def get_domain_dir(cls, domain='*'):
        key_dir = cls.authorized_keys_dir if domain == '*' else join(cls.base_dir, domain)
        return key_dir

    @staticmethod
    def secure_context(log, context=None, async=False):
        if async:
            ctx = context or zmq.asyncio.Context()
            auth = AsyncioAuthenticator(ctx)
            auth.log = log # The constructor doesn't have "log" like its synchronous counter-part
        else:
            ctx = context or zmq.Context()
            auth = ThreadAuthenticator(ctx, log=log)
        # auth.start()
        return ctx, auth

    @staticmethod
    def secure_socket(sock, secret, public_key, domain='*'):
        sock.curve_secretkey = secret
        sock.curve_publickey = public_key
        if domain != '*':
            sock.zap_domain = domain.encode()
        return sock


    @staticmethod
    def create_socket(ctx, socket_type, *args, **kwargs):
        socket = ctx.socket(socket_type, *args, **kwargs)
        # socket.setsockopt(zmq.LINGER, 200)              # ms - 200msec max
        # this should be modified at usage level, but a max limit at system level
        # raghu todo add this as configurable option in constants so tests can modify it if needed
        # socket.setsockopt(zmq.RCVTIMEO, 15000)           # 15 secs max
        # socket.setsockopt(zmq.SNDTIMEO, 15000)
        # socket.setsockopt(zmq.BACKLOG, n)       # number of peer connections - network size - 1 
        # socket.setsockopt(zmq.MAXMSGSIZE, b)       # protect your server from DoS - num of bytes
        # socket.setsockopt(zmq.RCVBUF, b)       # kernel receive buffer size - num of bytes - check SO_RCVBUF values?
        # socket.setsockopt(zmq.RCVHWM, 20)     # HWM - limit to the max of 20 messages. selectively increase it where needed
        # socket.setsockopt(zmq.CONNECT_TIMEOUT, 1500)
        if socket_type == zmq.ROUTER:
            socket.setsockopt(zmq.LINGER, 2000)              # ms - 200msec max
            socket.setsockopt(zmq.ROUTER_HANDOVER, 1)
            socket.setsockopt(zmq.ROUTER_MANDATORY, 1)

        return socket


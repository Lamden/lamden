import os, datetime, zmq, shutil, zmq.asyncio
from os.path import basename, splitext, join, exists
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
from cilantro.logger.base import get_logger
from cilantro.utils.keys import Keys

class SocketAuth:
    log = get_logger('SocketAuth')

    def __init__(self, reset_auth_folder=False):
        cls.keyname = cls.public_key.hex()
        cls.base_dir = 'certs/{}'.format(os.getenv('HOST_NAME', cls.keyname))
        cls.default_domain_dir = 'authorized_keys'
        cls.authorized_keys_dir = join(cls.base_dir, cls.default_domain_dir)
        if reset_auth_folder:
            cls.reset_folder()
        cls.add_public_key(public_key=cls.public_key)

    # only used locally - raghu
    @classmethod
    def reset_folder(cls):
        if exists(cls.base_dir):
            shutil.rmtree(cls.base_dir, ignore_errors=True)


    # can these be merged with handshake functionality
# handshake.py
# auth.py
    @classmethod
    def add_public_key(cls, public_key=None, vk=None, domain='*'):
        assert public_key or vk, 'No public key or vk provided'
        if vk: public_key = Keys.vk2pk(vk)
        public_key_filename = "{0}.key".format(public_key.hex())
        public_key_dir = join(cls.base_dir, cls.default_domain_dir if domain == '*' else domain)
        os.makedirs(public_key_dir, exist_ok=True)
        public_key_file = join(public_key_dir, public_key_filename)
        now = datetime.datetime.now()
        zmq.auth.certs._write_key_file(public_key_file,
                        zmq.auth.certs._cert_public_banner.format(now),
                        public_key)

    # can these be merged with handshake functionality
# handshake.py
# auth.py
    @classmethod
    def remove_public_key(cls, public_key=None, vk=None, domain='*'):
        assert public_key or vk, 'No public key or vk provided'
        if vk: public_key = Keys.vk2pk(vk)
        public_key_filename = "{0}.key".format(public_key)
        public_key_dir = join(cls.base_dir, cls.default_domain_dir if domain == '*' else domain)
        public_key_file = join(public_key_dir, public_key_filename)
        if exists(public_key_file):
            os.remove(public_key_file)

# /Users/lamden/lamden/cilantro/cilantro/protocol/comm/lsocket.py
# /Users/lamden/lamden/cilantro/cilantro/protocol/comm/socket_manager.py
    @classmethod
    def configure_auth(cls, auth, domain='*'):
        location = cls.authorized_keys_dir if domain == '*' else join(cls.base_dir, domain)
        auth.configure_curve(domain=domain, location=location)

# /Users/lamden/lamden/cilantro/cilantro/protocol/comm/socket_manager.py
# this should not be creating context again - raghu
# should be part of zmq/socket utils - raghu ?
    @classmethod
    def secure_context(cls, context=None, async=False):
        if async:
            ctx = context or zmq.asyncio.Context()
            auth = AsyncioAuthenticator(ctx)
            auth.log = cls.log # The constructor doesn't have "log" like its synchronous counter-part
        else:
            ctx = context or zmq.Context()
            auth = ThreadAuthenticator(ctx, log=log)
        auth.start()
        return ctx, auth

# /Users/lamden/lamden/cilantro/cilantro/protocol/comm/lsocket.py
# /Users/lamden/lamden/cilantro/cilantro/protocol/executors/dealer_router.py
# /Users/lamden/lamden/cilantro/cilantro/protocol/executors/sub_pub.py
# this should not be creating context again - raghu
# should be part of zmq/socket utils - raghu ?

    @classmethod
    def secure_socket(cls, sock, secret, public_key, domain='*'):
        sock.curve_secretkey = secret
        sock.curve_publickey = public_key
        if domain != '*':
            sock.zap_domain = domain.encode()
            public_key_dir = join(cls.base_dir, domain)
        else:
            public_key_dir = join(cls.base_dir, cls.default_domain_dir)
        os.makedirs(public_key_dir, exist_ok=True)
        return sock

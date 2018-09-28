import unittest
from unittest import TestCase
import zmq, zmq.asyncio, asyncio
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
from cilantro.protocol.overlay.ironhouse import Ironhouse
from zmq.utils.z85 import decode, encode
from os import listdir, makedirs
from os.path import exists
from threading import Timer
import asyncio, shutil
from cilantro.utils.test.overlay import *
from cilantro.constants.testnet import *
from tests.unit.protocol.overlay.ironhouse.base import TestIronhouseBase

def auth_validate(vk):
    print('Test: Received on validation: {}'.format(vk))
    return True

class TestValidate(TestIronhouseBase):
    def test_secure_server(self):
        ip = '127.0.0.1'
        port = 4523
        async def send_async_sec():
            client = self.ironhouse.ctx.socket(zmq.REQ)
            client = self.ironhouse.secure_socket(client, self.secret, self.curve_public_key, self.curve_public_key)
            client.connect('tcp://{}:{}'.format(ip, port))
            client.send(self.vk.encode())
            client.close()
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)


        self.ironhouse.setup_secure_server()
        self.assertIsInstance(self.ironhouse.ctx, zmq.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(self.ironhouse.sec_sock, zmq.sugar.socket.Socket, 'unable to secure a socket')

        self.loop.run_until_complete(
            asyncio.ensure_future(send_async_sec())
        )

    def test_authenticate(self):
        port = 5523
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertTrue(authorized)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.fake = genkeys('91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_authenticate_self(self):
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.curve_public_key, '127.0.0.1')
            self.assertTrue(authorized)
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.ironhouse.setup_secure_server()

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_authenticate_then_reject(self):
        port = 5523
        async def send_async_sec():
            await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.ironhouse.remove_public_key(self.fake['curve_key'])
            self.assertFalse(self.ironhouse.daemon_auth.certs['*'].get(self.fake['curve_key'], False))
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.fake = genkeys('91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_authenticate_fail(self):
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(b'A/c=Kn2)aHRI*>fK-{v*r^YCyXJ//3.CGQQC@A9J', '127.0.0.1')
            self.assertEqual(authorized, 'no_reply')
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.ironhouse.setup_secure_server()

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate(self):
        port = 5523
        self.validated = False
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertTrue(self.ironhouse.daemon_auth.certs['*'].get(self.fake['curve_key'], False))
            self.assertTrue(authorized)
            self.assertTrue(self.validated)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        def auth_validate_fake(vk):
            self.validated = True
            return True

        def auth_validate(vk):
            return vk == 'b9284b28589523f055ae5b54c98b0b904a1df3b0be5d546d30208d0516e71aa0'

        self.fake = genkeys('7ae3fcfd3a9047adbec6ad11e5a58036df9934dc0746431d80b49d25584d7e78')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.fake_ironhouse.auth_validate = auth_validate_fake
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])
        self.ironhouse.auth_validate = auth_validate

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate_default(self):
        port = 5523
        async def send_async_sec():
            authorized = await self.dih.authenticate(self.a['curve_key'], '127.0.0.1', port)
            self.assertTrue(authorized)
            self.aih.cleanup()
            self.dih.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.a = genkeys('5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c')
        self.aih = Ironhouse(self.a['sk'], auth_port=port, keyname='a')
        self.aih.setup_secure_server()
        self.aih.add_public_key(self.curve_public_key)

        self.dih = Ironhouse(self.sk)
        self.dih.setup_secure_server()
        self.dih.add_public_key(self.a['curve_key'])

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_invalid_public_key(self):
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(b'ack', '127.0.0.1', 1234)
            self.assertEqual(authorized, 'invalid')
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.ironhouse.setup_secure_server()

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate_fail_validate(self):
        port = 5523
        self.validated = False
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertEqual(authorized, 'unauthorized')
            self.assertTrue(self.validated)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        def auth_validate_fake(vk):
            self.validated = True
            return True

        def auth_validate(vk):
            return vk == b'catastrophe'

        self.fake = genkeys('7ae3fcfd3a9047adbec6ad11e5a58036df9934dc0746431d80b49d25584d7e78')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.fake_ironhouse.auth_validate = auth_validate_fake
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])
        self.ironhouse.auth_validate = auth_validate

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate_fail_timeout(self):
        port = 5523
        self.validated = False
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertEqual(authorized, 'no_reply')
            self.assertTrue(self.validated)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        def auth_validate_fake(vk):
            self.validated = True
            return False

        def auth_validate(vk):
            return vk == b'catastrophe'

        self.fake = genkeys('7ae3fcfd3a9047adbec6ad11e5a58036df9934dc0746431d80b49d25584d7e78')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.fake_ironhouse.auth_validate = auth_validate_fake
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])
        self.ironhouse.auth_validate = auth_validate


        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_cleanup(self):
        async def delay():
            await asyncio.sleep(0.1)
            del self.ironhouse
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.loop.run_until_complete(
            asyncio.ensure_future(
                delay()
            )
        )

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()

from cilantro import Constants
from cilantro.utils.test import MPTesterBase, mp_testable
from unittest.mock import patch, call, MagicMock
from cilantro.protocol.transport import Router, Composer
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.statemachine import StateMachine
import asyncio


@mp_testable(Composer)
class MPComposer(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, name='') -> tuple:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_sm = MagicMock(spec=StateMachine)
        mock_sm.__name__ = name
        router = MagicMock()

        reactor = ReactorInterface(router=router, loop=loop, verifying_key=Constants.Protocol.Wallets.get_vk(sk))
        composer = Composer(interface=reactor, signing_key=sk)

        asyncio.ensure_future(reactor._recv_messages())

        return composer, loop


# @mp_testable(God)
# class MPGod(MPTesterBase):
#     @classmethod
#     def build_obj(cls):
#         loop = asyncio.new_event_loop()
#         god = God(loop=loop)
#         god.start()
#
#         return god, loop
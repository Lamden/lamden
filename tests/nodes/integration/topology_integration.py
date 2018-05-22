from cilantro.utils.test import *
from cilantro.nodes import *
from cilantro.utils.test import MPTesterBase, MPTestCase, mp_testable
from unittest.mock import patch, call, MagicMock
import asyncio


"""
Here we do integration tests on our network topology. We spin up nodes on the VM, and ensure that they can talk
to each other how we expect them to.
"""


@mp_testable(God)
class MPGod(MPTesterBase):
    @classmethod
    def build_obj(cls):
        loop = asyncio.new_event_loop()
        god = God(loop=loop)
        god.start()

        return god, loop


@mp_testable(Masternode)
class MPMasterNode(MPTesterBase):
    @classmethod
    def build_obj(cls):
        pass

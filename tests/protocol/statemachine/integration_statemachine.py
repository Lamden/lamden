from unittest import TestCase
from unittest.mock import MagicMock
from .trafficlight import *
from cilantro.utils.test import MPTestCase, MPStateMachine
from .stumachine import *


class IntegrationTestState(MPTestCase):

    def test_state_timeout(self):
        def assert_fn(sm):
            assert sm.state == ChillState

        stu = MPStateMachine(sm_class=StuMachine, assert_fn=assert_fn)

        stu.start()
        stu.transition('FactorioState')

        self.start()


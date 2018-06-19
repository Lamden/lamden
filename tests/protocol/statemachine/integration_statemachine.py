from unittest import TestCase
from unittest.mock import MagicMock
from .trafficlight import *
from cilantro.utils.test import MPTestCase, MPStateMachine
from .stumachine import StuMachine


class IntegrationTestState(MPTestCase):

    def test_state_timeout(self):
        stu = MPStateMachine(sm_class=StuMachine)

        stu.start()
        stu.transition('FactorioState')


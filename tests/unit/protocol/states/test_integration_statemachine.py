from cilantro.utils.test.mp_test_case import MPTestCase
from cilantro.utils.test.mp_testables import MPStateMachine
import time, unittest
try:
    from .stumachine import *
except:
    from stumachine import *


class IntegrationTestState(MPTestCase):

    def test_state_timeout(self):
        def assert_fn(sm):
            assert sm.state == ChillState
            assert sm.did_timeout

        stu = MPStateMachine(sm_class=StuMachine, assert_fn=assert_fn)

        stu.start()
        stu.transition('FactorioState')

        self.start()

    def test_state_timeout_interrupted(self):
        def assert_fn(sm):
            # Assert that he got out of Factorio state
            assert not sm.did_timeout
            assert sm.state != FactorioState

            # Assert that he went into lift state with the specified args
            assert sm.state == LiftState
            assert sm.state.current_lift == LiftState.DEADLIFT
            assert sm.state.current_weight == 9000

        stu = MPStateMachine(sm_class=StuMachine, assert_fn=assert_fn)

        stu.start()
        stu.transition('FactorioState')
        time.sleep(0.5)  # transition out before the timeout
        stu.transition(LiftState, lift=LiftState.DEADLIFT, weight=9000)

        self.start()

if __name__ == '__main__':
    unittest.main()

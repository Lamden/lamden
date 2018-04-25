from unittest import TestCase
import time
from cilantro.logger import get_logger
from cilantro.utils.test.thicc_test import TTBase, SIG_ABORT, SIG_FAIL, SIG_RDY, SIG_SUCC

TEST_TIMEOUT = 5
TEST_POLL_FREQ = 0.25


class ThiccTestCase(TestCase):

    def setUp(self):
        super().setUp()
        assert len(TTBase.testers) == 0, "setUp called but TTBase._testers is not empty ({})".format(TTBase.testers)
        # print("---- set up called ----")

    def tearDown(self):
        super().tearDown()
        TTBase.testers.clear()
        # print("%%%% TEARDOWN CALLED %%%%%")
        # self.log.critical("ACTIVE TESTERS: {}".format(TTBase.testers))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("ThiccTester")

    def start(self):
        # self.log.critical("\nSTARTING TEST WITH TESTERS {}\n".format(TTBase.testers))
        assert len(TTBase.testers) > 0, "start() called, but list of testers empty (TTBase._testers={})"\
                                         .format(TTBase.testers)

        # We organize all registered testers into 'active' testers, which are passed in an assertions function,
        # and 'passive' testers which do not make assertions but still interact with other testers.
        # Testers' output queues are polled  every TEST_POLL_FREQ seconds for maximum of TEST_TIMEOUT seconds,
        # waiting for them to finish (if ever). When an 'active' testers passes its assertions, we move it to
        # 'passives'. When all active testers are finished, we send ABORT_SIGs to all testers to clean them up
        actives, passives, fails, timeout = self._poll_testers()

        self.log.debug("Cleaning up tester processes")
        for t in actives + passives + fails:
            t.cmd_q.put(SIG_ABORT)
            t.teardown()

        # If there are no active testers left and none of them failed, we win
        if len(actives) + len(fails) == 0:
            self.log.critical("\n\n{0}\n\n\t\t\tTESTERS SUCCEEDED WITH {1} SECONDS LEFT\n\n{0}\n"
                              .format('$' * 120, timeout))
        else:
            fail_msg = "\nfail_msg:\n{0}\nTESTS TIMED OUT FOR TESTERS: \n\n".format('-' * 120)
            for t in fails + actives:
                fail_msg += "{}\n".format(t)
            fail_msg += "{0}\n".format('-' * 120)
            self.log.critical(fail_msg)
            raise Exception()

    def _poll_testers(self) -> tuple:
        actives = [t for t in TTBase.testers if t.assert_fn]
        passives = [t for t in TTBase.testers if not t.assert_fn]
        fails = []

        timeout = TEST_TIMEOUT
        while timeout > 0:
            for t in actives:
                try:
                    msg = t.sig_q.get_nowait()
                    self.log.critical("\n\nGOT MSG {} FROM TESTER <{}>\n".format(msg, t))
                    actives.remove(t)
                    if msg == SIG_SUCC:
                        passives.append(t)
                    else:
                        fails.append(t)
                except Exception as e:
                    pass

            # Break if all active testers have finished
            if len(actives) == 0:
                self.log.debug("Breaking from loop, no active tester left")
                break

            # Sleep for TEST_POLL_FREQ seconds
            timeout -= TEST_POLL_FREQ
            time.sleep(TEST_POLL_FREQ)

        return actives, passives, fails, timeout

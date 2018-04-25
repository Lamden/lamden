import asyncio
import zmq.asyncio

import time
import os
import shutil
import sys
import dill

from unittest import TestCase
from cilantro.logger import get_logger
from cilantro.utils.test.mp_test import MPTesterBase, SIG_ABORT, SIG_FAIL, SIG_RDY, SIG_SUCC

# URL of orchestration node. TODO -- set this to env vars
URL = "tcp://127.0.0.1:5020"

TEST_TIMEOUT = 5
TEST_POLL_FREQ = 0.25


class MPTestCase(TestCase):
    # TODO -- define this stuff in subclass
    testname = 'cilantro_pub_sub'
    project = 'cilantro'
    compose_file = '/Users/davishaba/Developer/Lamden/vmnet/tests/configs/cilantro-pub-sub.yml'
    docker_dir = '/Users/davishaba/Developer/Lamden/vmnet/docker/docker_files/cilantro'
    logdir = '/Users/davishaba/Developer/Lamden/cilantro/logs'
    waittime = 15
    _is_setup = False

    def run_script(self, params):
        """
            Runs launch.py to start-up or tear-down for network of nodes in the
            specifed Docker network.
        """
        launch_path = '/Users/davishaba/Developer/Lamden/vmnet/docker/launch.py'
        os.system('python {} --project {} {}'.format(
            launch_path,
            self.project,
            params
        ))

    def execute_python(self, node, fn, async=True, python_version='3.6'):
        fn_str = dill.dumps(fn, 0)
        exc_str = 'docker exec {} /usr/bin/python{} -c \"import dill; fn = dill.loads({}); fn();\" {}'.format(
            node,
            python_version,
            fn_str,
            '&' if async else ''
        )
        os.system(exc_str)
        # self.collect_log()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("MPTestOrchestrater")

        # TODO set this propertly (maybe decorator?)
        self.project = 'cilantro'

    def setUp(self):
        super().setUp()
        assert len(MPTesterBase.testers) == 0, "setUp called but MPTesterBase._testers is not empty ({})"\
                                                .format(MPTesterBase.testers)

        if not self._is_setup:
            self.__class__._is_setup = True
            self.testdir = '{}/{}'.format(self.logdir, self.testname)
            try: shutil.rmtree(self.testdir)
            except: pass
            os.environ['TEST_NAME'] = self.testname
            self.run_script('--clean')
            self.run_script('--compose_file {} --docker_dir {} &'.format(
                self.compose_file,
                self.docker_dir
            ))
            print('Running test "{}" and waiting for {}s...'.format(self.testname, self.waittime))
            time.sleep(self.waittime)
            sys.stdout.flush()
        # print("---- set up called ----")

    def tearDown(self):
        super().tearDown()
        MPTesterBase.testers.clear()
        # print("%%%% TEARDOWN CALLED %%%%%")
        # self.log.critical("ACTIVE TESTERS: {}".format(MPTesterBase.testers))

    def start(self):
        # self.log.critical("\nSTARTING TEST WITH TESTERS {}\n".format(MPTesterBase.testers))
        assert len(MPTesterBase.testers) > 0, "start() called, but list of testers empty (MPTesterBase._testers={})"\
                                         .format(MPTesterBase.testers)

        # We organize all registered testers into 'active' testers, which are passed in an assertions function,
        # and 'passive' testers which do not make assertions but still interact with other testers.
        # Testers' output queues are polled  every TEST_POLL_FREQ seconds for maximum of TEST_TIMEOUT seconds,
        # waiting for them to finish (if ever). When an 'active' testers passes its assertions, we move it to
        # 'passives'. When all active testers are finished, we send ABORT_SIGs to all testers to clean them up
        actives, passives, fails, timeout = self._poll_testers()

        self.log.debug("Cleaning up tester processes")
        for t in actives + passives + fails:
            # t.cmd_q.put(SIG_ABORT)
            t.socket.send_pyobj(SIG_ABORT)
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
        actives = [t for t in MPTesterBase.testers if t.assert_fn]
        passives = [t for t in MPTesterBase.testers if not t.assert_fn]
        fails = []

        timeout = TEST_TIMEOUT
        while timeout > 0:
            for t in actives:
                try:
                    msg = t.socket.recv(flags=zmq.NOBLOCK)
                    self.log.critical("\nGOT MSG {} FROM TESTER <{}>\n".format(msg, t))
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

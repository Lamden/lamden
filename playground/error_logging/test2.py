from cilantro.logger import get_logger
from multiprocessing import Process
import asyncio
import time
import traceback
import inspect

DELIM_LEN = 60
OUTER_DELIM = '!'
INNER_DELIM = '-'

class LProcess(Process):
    def run(self):
        log = get_logger(self.name)
        log.info("---> {} Starting --->".format(self.name))

        try:
            super().run()
        except Exception as e:
            err_msg = '\n' + OUTER_DELIM * DELIM_LEN
            err_msg += '\nException caught on ' + self.name + ':\n' + str(e)
            err_msg += '\n' + INNER_DELIM * DELIM_LEN
            err_msg += '\n' + traceback.format_exc()
            err_msg += '\n' + INNER_DELIM * DELIM_LEN
            err_msg += '\n' + OUTER_DELIM * DELIM_LEN
            log.error(err_msg)
        finally:
            log.info("<--- {} Terminating <---".format(self.name))
            # TODO -- signal to parent to call .join() on this process to clean up nicely


def sub_sub_proc_start():
    log = get_logger("SubSubProc")
    log.debug("sub sub proc created, sleeping now")
    time.sleep(2)
    log.debug("sub sub proc done sleeping now")

    # i = 10 / 0


def sub_proc_start():
    SLEEP_TIME = 10
    log = get_logger("SubProc")

    # log.debug("subproc spinning up subsubproc")
    p = LProcess(target=sub_sub_proc_start)
    p.daemon = True
    p.start()

    log.debug("sleeping for {}".format(SLEEP_TIME))
    time.sleep(SLEEP_TIME)
    log.debug("Done sleeping")


def proc_start():
    SLEEP_TIME = 3
    log = get_logger("ProcStart")

    log.debug("proc starting subproc")
    p = LProcess(target=sub_proc_start)
    p.daemon = True
    p.start()
    log.debug("subproc started")


    # time.sleep(0.1)

    # p.join()

    # log.critical("!!!!\n!!!!!\nABOUT TO EXPLODE\n!!!!!\n!!!!!")
    # i = 10 / 0





if __name__ == '__main__':
    log = get_logger('MAIN')
    print("\n\n\n THIS IS A PRINT LETS GOOOOOO \n\n\n")


    log.info("starting process")
    p = LProcess(target=proc_start)
    p.start()

    print("hi this is a test")
    print("lets go my friend")
    # i = 10 / 0


from cilantro.logger import get_logger
import traceback
from pympler import muppy, summary
from multiprocessing import Process
import sys
from io import StringIO
import os


def mup_dat(filename):
    oo = muppy.get_objects()
    s = summary.summarize(oo)

    # Intercept stdout
    old_stdout = sys.stdout
    
    summary.print_(s)


def get_filename(proc_name):
    prefix = os.getenv('HOSTNAME', '')
    if prefix:
        return prefix + '_' + proc_name
    else:
        return proc_name



DELIM_LEN = 60
OUTER_DELIM = '!'
INNER_DELIM = '-'


class LProcess(Process):
    def run(self):
        log = get_logger(self.name)
        log.info("---> {} Starting --->".format(self.name))

        try:
            log.critical("\nMup dat before running process {}\n".format(self.name))
            mup_dat()
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
            log.critical("\nMup dat after teardown of {}\n".format(self.name))
            mup_dat()
            # TODO -- signal to parent to call .join() on this process and clean up nicely
from cilantro.logger import get_logger
import traceback
from multiprocessing import Process
import os
import cProfile


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
    def regRun(self):
        super().run()

    def profRun(self, filename):
        cProfile.runctx('self.regRun()', globals(), locals(), filename)

    def run(self):
        log = get_logger(self.name)
        log.info("---> {} Starting --->".format(self.name))
        try:
            f = get_filename(self.name)
            gen_profile = os.getenv('LAMDEN_PERF_PROFILE', '1')
            if gen_profile != '0':
                self.profRun(f)
            else:
                self.regRun()
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
            # TODO -- signal to parent to call .join() on this process and clean up nicely
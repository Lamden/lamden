from cilantro.logger import get_logger
from multiprocessing import Process
import traceback


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
            # TODO -- signal to parent to call .join() on this process and clean up nicely

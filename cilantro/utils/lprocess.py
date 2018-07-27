from cilantro.logger import get_logger
import traceback
from pympler import muppy, summary
from multiprocessing import Process
from threading import Thread
import sys
import asyncio
from io import StringIO
import os
import time
import csv


def get_filename(proc_name):
    prefix = os.getenv('HOSTNAME', '')
    if prefix:
        return prefix + '_' + proc_name
    else:
        return proc_name


DELIM_LEN = 60
OUTER_DELIM = '!'
INNER_DELIM = '-'


# def profile_process(interval, name):
#     while True:
#         log = get_logger(name)
#         o = muppy.get_objects()
#         size = muppy.get_size(o)
#         log.critical("---> {} : USING {} BYTES --->".format(name, size))
#         header = ['unix_time', 'size']
#
#         filename = name + '.csv'
#
#         file_exists = os.path.isfile(filename)
#
#         with open(filename, 'a') as csvfile:
#             writer = csv.DictWriter(csvfile, delimiter=',', lineterminator='\n', fieldnames=header)
#
#             if not file_exists:
#                 writer.writeheader()  # file doesn't exist yet, write a header
#
#             writer.writerow({'unix_time': time.time(), 'size': size})
#
#         time.sleep(interval)


class LProcess(Process):
    def run(self):
        log = get_logger(self.name)
        log.info("---> {} Starting --->".format(self.name))
        try:
            # f = get_filename(self.name)
            # t = Thread(target=profile_process, args=(1, f))
            # t.start()
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
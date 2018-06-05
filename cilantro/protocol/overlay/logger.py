import logging
import os
import sys

class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            self.level(message)

    def flush(self):
        return

def get_logger(name=''):
    filedir = "logs/{}".format(os.getenv('TEST_NAME', 'test'))
    filename = "{}/{}.log".format(filedir, os.getenv('HOSTNAME', name))
    os.makedirs(filedir, exist_ok=True)
    filehandlers = [
        logging.FileHandler(filename),
        logging.StreamHandler()
    ]
    logging.basicConfig(
        format="%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s",
        handlers=filehandlers,
        level=logging.DEBUG
    )
    err_log = logging.getLogger("STDERR")
    sys.stderr = LoggerWriter(err_log.error)
    return logging.getLogger(name)

"""Module for initializing settings related to the built-in Cilantro logger

Functions:
-get_logger"""


import os
from pathlib import Path
import logging, coloredlogs
from logging.config import fileConfig
import sys

global get_logger

REDIRECT_STDOUT = True
# Class to bridge a stream and a logger. We use this to write stdout/stderr to our log files
class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            self.level(message)

    def flush(self):
        return

if not os.getenv('TEST_NAME'):
    # True will output stdout/stderr to log files however we lose support of colored logging in the PyCharm console
    # False does not output stdout/stderr to log files, but will retain coloring in PyCharm console
    # This is a temporary solution. Only reason we can't have both is because I can't figure out how :sigh:

    # Constants for configuring colored logger
    lvl_styles = coloredlogs.DEFAULT_LEVEL_STYLES
    COLORS = ('blue', 'cyan', 'green', 'magenta', 'red', 'yellow', 'white')
    LVLS = ('debug', 'info', 'warning', 'error', 'critical')
    P = pow(2, 31) - 1


    def get_logger(name='', bg_color=None, auto_bg_val=None):
        def apply_bg_color(lvls, color):
            for lvl in lvls:
                lvl_styles[lvl]['background'] = color
                lvl_styles[lvl]['color'] = 'black'

        if auto_bg_val is not None:
            assert bg_color is None, "Cannot set both bg_color and auto_bg_val (must be one or the other)"
            color = COLORS[(auto_bg_val*P) % len(COLORS)]
            apply_bg_color(LVLS, color)

        if bg_color is not None:
            assert auto_bg_val is None, "Cannot set both bg_color and auto_bg_val (must be one or the other)"
            apply_bg_color(LVLS, bg_color)

        log = logging.getLogger(name)

        if REDIRECT_STDOUT:
            coloredlogs.install(level='DEBUG', logger=log, level_styles=lvl_styles, milliseconds=True, reconfigure=False)
            # Remove all handlers
            for h in log.handlers:
                log.removeHandler(h)
        else:
            coloredlogs.install(level='DEBUG', logger=log, level_styles=lvl_styles, milliseconds=True, reconfigure=True)

        return log

    # Configure logger from config file cilantro/conf/cilantro_logger.ini
    path = os.path.dirname(Path(__file__).parents[0])
    os.makedirs(os.path.join(os.path.dirname(path), 'logs'), exist_ok=True)
    os.chdir(path)
    path += "/conf"
    loggerIniFile = path + "/cilantro_logger.ini"
    fileConfig(loggerIniFile)

    # Forward stderr/stdout to loggers (so prints and exceptions can be seen in log files)
    if REDIRECT_STDOUT:
        out_log = logging.getLogger('STDOUT')
        err_log = logging.getLogger("STDERR")
        sys.stderr = LoggerWriter(err_log.error)
        sys.stdout = LoggerWriter(out_log.debug)
else:
    def get_logger(name='', bg_color=None, auto_bg_val=None):
        import logging
        import os
        import sys
        filedir = "logs/{}".format(os.getenv('TEST_NAME'))
        filename = "{}/{}.log".format(filedir, os.getenv('HOSTNAME'))
        os.makedirs(filedir, exist_ok=True)
        filehandlers = [logging.FileHandler(filename)]
        logging.basicConfig(
            format="%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s",
            handlers=filehandlers,
            level=logging.DEBUG
        )
        return logging.getLogger(name)
    if REDIRECT_STDOUT:
        out_log = logging.getLogger('STDOUT')
        err_log = logging.getLogger("STDERR")
        sys.stderr = LoggerWriter(err_log.error)
        sys.stdout = LoggerWriter(out_log.debug)

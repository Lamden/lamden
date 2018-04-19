import os
from pathlib import Path
import logging, coloredlogs
from logging.config import fileConfig
import sys


lvl_styles = coloredlogs.DEFAULT_LEVEL_STYLES
COLORS = ('blue', 'cyan', 'green', 'magenta', 'red', 'yellow', 'white')
LVLS = ('debug', 'info', 'warning', 'error', 'critical')

P = pow(2, 31) - 1


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass


path = os.path.dirname(Path(__file__).parents[0])
os.chdir(path)
path += "/conf"
loggerIniFile = path + "/cilantro_logger.ini"
fileConfig(loggerIniFile)


# Configure stdout and stderr to use loggers
stdout_logger = logging.getLogger('STDOUT')
out_log = StreamToLogger(stdout_logger, logging.INFO)
# sys.stdout = out_log

stderr_logger = logging.getLogger('STDERR')
err_log = StreamToLogger(stderr_logger, logging.ERROR)
# sys.stderr = err_log


# LVL_STYLES = coloredlogs.DEFAULT_LEVEL_STYLES
# LVL_STYLES['critical']['background'] = 'blue'

def get_logger(name: str, bg_color=None, auto_bg_val=None):
    def apply_bg_color(lvls, color):
        for lvl in lvls:
            lvl_styles[lvl]['background'] = color
            lvl_styles[lvl]['color'] = 'black'
            # if ('color' in lvl_styles[lvl]) and (lvl_styles[lvl]['color'] == color):
            #     lvl_styles[lvl]['color'] = 'white'

    if auto_bg_val is not None:
        assert bg_color is None, "Cannot set both bg_color and auto_bg_val (must be one or the other)"
        color = COLORS[(auto_bg_val*P) % len(COLORS)]
        apply_bg_color(LVLS, color)

    if bg_color is not None:
        assert auto_bg_val is None, "Cannot set both bg_color and auto_bg_val (must be one or the other)"
        apply_bg_color(LVLS, bg_color)

    log = logging.getLogger(name)
    coloredlogs.install(level='DEBUG', logger=log, level_styles=lvl_styles, milliseconds=True)

    return log


print("this is a test")

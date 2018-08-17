import logging, coloredlogs
import os, sys

VALID_LVLS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
_LOG_LVL = os.getenv('LOG_LEVEL', None)
if _LOG_LVL:
    assert _LOG_LVL in VALID_LVLS, "Log level {} not in valid levels {}".format(_LOG_LVL, VALID_LVLS)
    _LOG_LVL = getattr(logging, _LOG_LVL)
else:
    _LOG_LVL = 1

format = '%(asctime)s.%(msecs)03d %(name)s[%(process)d][%(processName)s] %(levelname)-2s %(message)s'

CUSTOM_LEVELS = {
    'SPAM': 1,
    'DEBUGV': 5,
    'NOTICE': 24,
    'SUCCESS': 26,
    'IMPORTANT': 56,
    'IMPORTANT2': 57,
    'IMPORTANT3': 58,
    'FATAL': 9001,
    }

for log_name, log_level in CUSTOM_LEVELS.items():
    logging.addLevelName(log_level, log_name)

def apply_custom_level(log, name: str, level: int):
    def _lvl_func(message, *args, **kws):
        if level >= log.getEffectiveLevel():
            log._log(level, message, args, **kws)

    setattr(log, name.lower(), _lvl_func)

"""
Custom Styling
"""

coloredlogs.DEFAULT_LEVEL_STYLES = {
    'critical':{'color':'white', 'bold':True, 'background': 'red'},
    'fatal':{'color':'white', 'bold':True, 'background': 'red', 'underline': True},
    'debug':{'color':'green' },
    'error':{'color':'red' },
    'info':{'color':'white' },
    'notice':{'color':'magenta' },
    'important':{ 'color':'cyan', 'bold': True, 'background': 'magenta'},
    'important2':{ 'color':'magenta', 'bold': True, 'background': 'cyan'},
    'important3':{ 'color':'black', 'bold': True, 'background': 'yellow'},
    'spam':{ 'color':'white', 'faint':True },
    'success':{'color':'white', 'bold': True, 'background': 'green'},
    'verbose':{'color':'blue' },
    'warning':{'color':'yellow' },
    'debugv':{'color':'blue', 'faint':True }
}
coloredlogs.DEFAULT_FIELD_STYLES = {
    'asctime': {'color': 'green'},
    'hostname': {'color': 'magenta'},
    'levelname': {'color': 'black', 'bright': True},
    'name': {'color': 'blue'},
    'programname': {'color': 'cyan'}
}

class LoggerWriter:
    def __init__(self, level):
        self.level = level
    def write(self, message):
        if message != '\n':
            self.level(message)
    def flush(self):
        return

class ColoredFileHandler(logging.FileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFormatter(
            coloredlogs.ColoredFormatter(format)
        )

class ColoredStreamHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFormatter(
            coloredlogs.ColoredFormatter(format)
        )

def get_logger(name=''):
    filedir = "logs/{}".format(os.getenv('TEST_NAME', 'test'))
    filename = "{}/{}.log".format(filedir, os.getenv('HOST_NAME', name))
    os.makedirs(filedir, exist_ok=True)

    filehandlers = [
        logging.FileHandler(filename),
        ColoredFileHandler('{}_color'.format(filename)),
        ColoredStreamHandler()
    ]
    
    logging.basicConfig(
        format=format,
        handlers=filehandlers,
        level=logging.DEBUG
    )

    log = logging.getLogger(name)
    log.setLevel(_LOG_LVL)

    sys.stdout = LoggerWriter(log.debug)
    sys.stderr = LoggerWriter(log.error)

    for log_name, log_level in CUSTOM_LEVELS.items():
        apply_custom_level(log, log_name, log_level)

    return log

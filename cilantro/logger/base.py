"""Module for initializing settings related to the built-in seneca logger
Functions:
-get_logger"""

import logging, coloredlogs
import os, sys
from os.path import dirname
from logging.handlers import TimedRotatingFileHandler
import cilantro
from vmnet.cloud.aws import S3Handlers

logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

VALID_LVLS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
_LOG_LVL = os.getenv('LOG_LEVEL', None)
if _LOG_LVL:
    assert _LOG_LVL in VALID_LVLS, "Log level {} not in valid levels {}".format(_LOG_LVL, VALID_LVLS)
    _LOG_LVL = getattr(logging, _LOG_LVL)
else:
    _LOG_LVL = 1

req_log = logging.getLogger('urllib3')
req_log.setLevel(logging.WARNING)
req_log.propagate = True


def get_main_log_path():
    import cilantro

    root = cilantro.__file__  # resolves to '/Users/davishaba/Developer/cilantro/cilantro/__init__.py'
    log_path = '/'.join(root.split('/')[:-2]) + '/logs/cilantro.log'

    # Create log directory if it does not exist
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    return log_path

format = '%(asctime)s.%(msecs)03d %(name)s[%(process)d][%(processName)s] <{}> %(levelname)-2s %(message)s'.format(os.getenv('HOST_NAME', 'Node'))

"""
Custom Log Levels
"""

CUSTOM_LEVELS = {
    'SPAM': 1,
    'DEBUGV': 5,
    'SOCKET': 23,
    'NOTICE': 24,
    'SUCCESS': 26,
    'SUCCESS2': 27,
    'IMPORTANT': 56,
    'IMPORTANT2': 57,
    'IMPORTANT3': 58,
    'FATAL': 9001,
    'TEST': 9002,
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
    'critical': {'color': 'white', 'bold': True, 'background': 'red'},
    'fatal': {'color': 'white', 'bold': True, 'background': 'red', 'underline': True},
    'debug': {'color': 'green'},
    'error': {'color': 'red'},
    'info': {'color': 'white'},
    'notice': {'color': 'magenta'},
    'test': {'color': 'magenta'},
    'socket': {'color': 216},
    'important': {'color': 'cyan', 'bold': True, 'background': 'magenta'},
    'important2': {'color': 'magenta', 'bold': True, 'background': 'cyan'},
    'important3': {'color': 'black', 'bold': True, 'background': 'yellow'},
    'spam': {'color': 'white', 'faint': True},
    'success': {'color': 'white', 'bold': True, 'background': 'green'},
    'success2': {'color': 165, 'bold': True, 'background': 'green'},
    'verbose': {'color': 'blue'},
    'warning': {'color': 'yellow'},
    'debugv': {'color': 'blue', 'faint': False}
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


class ColoredFileHandler(TimedRotatingFileHandler):
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

def _ignore(*args, **kwargs):
    return


class MockLogger:
    def __getattr__(self, item):
        return _ignore

def get_logger(name=''):
    if _LOG_LVL == 0:
        return MockLogger()

    filedir = "{}/logs/{}".format(dirname(cilantro.__path__[0]), os.getenv('TEST_NAME', 'test'))
    filename = "{}/{}.log".format(filedir, os.getenv('HOST_NAME', name))

    if not os.path.exists(filedir):
        os.makedirs(filedir, exist_ok=True)

    filehandlers = [
        ColoredFileHandler('{}_color'.format(filename), delay=True, when="m", interval=30, backupCount=5),
        ColoredStreamHandler()
    ]

    if os.getenv('VMNET_CLOUD'):
        s3h = S3Handlers()
        filehandlers += [s3h.out_logger, s3h.err_logger]

    logging.basicConfig(
        format=format,
        handlers=filehandlers,
        level=logging.DEBUG
    )

    log = logging.getLogger(name)
    log.setLevel(_LOG_LVL)

    if os.getenv('VMNET_DOCKER') or os.getenv('VMNET_CLOUD'):
        sys.stdout = LoggerWriter(log.debug)
        sys.stderr = LoggerWriter(log.error)

    for log_name, log_level in CUSTOM_LEVELS.items():
        apply_custom_level(log, log_name, log_level)

    return log


def overwrite_logger_level(level):
    global _LOG_LVL
    _LOG_LVL = level

    for name in logging.Logger.manager.loggerDict.keys():
        log = logging.getLogger(name)
        log.setLevel(level)

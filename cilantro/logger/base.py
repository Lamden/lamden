import os
from pathlib import Path
import logging, coloredlogs
from logging.config import fileConfig

path = os.path.dirname(Path(__file__).parents[0])
os.chdir(path)
path += "/conf"
loggerIniFile = path + "/cilantro_logger.ini"
fileConfig(loggerIniFile)

def get_logger(name: str):
    log = logging.getLogger(name)
    coloredlogs.install(level='DEBUG')
    coloredlogs.install(level='DEBUG', logger=log)

    return log

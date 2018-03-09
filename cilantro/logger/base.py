import os
from pathlib import Path
import logging
from logging.config import fileConfig

path = os.path.dirname(Path(__file__).parents[0])
os.chdir(path)
path += "/conf"
loggerIniFile = path + "/cilantro_logger.ini"
fileConfig(loggerIniFile)

def get_logger(name: str):
    return logging.getLogger(name)

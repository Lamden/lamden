import os
from pathlib import Path
import logging
from logging.config import fileConfig

def get_logger():
    """
    Initalizes a logger object configured based on cilantro_logger.ini
    :return: logger object
    """
    path = os.path.dirname(Path(__file__).parents[0])
    os.chdir(path)
    path += "/conf"
    loggerIniFile = path + "/cilantro_logger.ini"
    fileConfig(loggerIniFile)
    return logging.getLogger()

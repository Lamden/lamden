import logging
from contracting.db.driver import FSDriver
import pathlib

STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')


class SystemDriver:
    def __init__(self, driver=FSDriver(root=STORAGE_HOME.joinpath('sys'))):
        self.driver = driver
        self.log = logging.getLogger('SuperDriver')

    def set(self, key, value):
        self.driver.set(key, value)

    def get(self, key, value):
        pass
from cilantro.logger import get_logger


"""
This class is a drop-in mixin to add support for pickling objects that have loggers. By default, loggers are not
picklable (basically b/c they use some non-picklable lock objects), thus any logger objects must be removed from the
object before they are pickled, and recreated when they are unloaded. 
"""

LOG_NAME = 'log'


class PicklableMixin:
    def __getstate__(self):
        d = self.__dict__.copy()
        if LOG_NAME in d:
            d[LOG_NAME] = d[LOG_NAME].name
        return d

    def __setstate__(self, d):
        if LOG_NAME in d:
            d[LOG_NAME] = get_logger(d[LOG_NAME])
        self.__dict__.update(d)

def _lp_name(fn_name):
    """
    Helper function to get the internal lazy property name of a property
    :param fn: The name of the property function to be decorated
    :return: The property name prefixed by '_lazy_'
    """
    return '_lazy_' + fn_name


def set_lazy_property(obj, fn_name, value):
    """
    Convenience method to set the value of a lazy property before it is read. In the case that the value is known ahead
    of time, this should be implement to improve performance
    :param obj: The object the lazy property should be set on
    :param fn_name: The name of the property function to be set as a string
    :param value: The value to set the property to
    """
    attr_name = _lp_name(fn_name)
    setattr(obj, attr_name, value)


def lazy_property(fn):
    """
    Decorator that makes a property lazy-evaluated.
    :param fn: The property function to be decorated
    """
    attr_name = _lp_name(fn.__name__)

    @property
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    return _lazy_property


def lazy_func(fn):
    """
    Slap this decorator on a func and memoize it (assumes func has no input or is called with same input every time)
    """
    func_name = _lp_name(fn.__name__)

    def _cache_func(self, *args, **kwargs):
        if not hasattr(self, func_name):
            setattr(self, func_name, fn(self, *args, **kwargs))
        return getattr(self, func_name)

    return _cache_func


# def set_lazy_func(obj, fn, value):
#     func_name = _lp_name(fn.__name__)
#
#     def _cache_func(*args, **kwargs):
#         return value
#
#     setattr(obj, func_name, _cache_func)

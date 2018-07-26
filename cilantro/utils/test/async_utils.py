import asyncio, time
from threading import Timer

def async_run_for(delay):
    def _run(fn, *arg, **kwargs):
        loop = asyncio.new_event_loop()
        def _stop():
            loop.call_soon_threadsafe(loop.stop)
        def _fn(self):
            stopper = Timer(delay, _stop)
            stopper.start()
            fn(self, loop)
            loop.run_forever()
        return _fn
    return _run

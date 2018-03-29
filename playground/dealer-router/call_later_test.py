import asyncio
import time
from cilantro.logger import get_logger

log = get_logger("Main")

def do_something(msg):
    log.critical("doing something with msg {}".format(msg))

if __name__ == "__main__":
    log.debug("Main started")

    loop = asyncio.get_event_loop()
    # asyncio.set_event_loop(loop)

    log.info("About to schedule later")
    loop.call_later(1.0, do_something, "this is the msg")
    log.info("ok its scheduled")

    while True:
        time.sleep(0.2)
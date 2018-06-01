import asyncio
import time
from cilantro.logger import get_logger

log = get_logger("Main")

def do_something(msg):
    log.critical("\n!!!\ndoing something with msg {}\n!!!\n".format(msg))

async def something_long(future):
    log.critical("starting a long thing")
    time.sleep(1.0)
    log.critical("done with a long thing")

    log.critical("canceling future after that long thing")
    future.cancel()

if __name__ == "__main__":
    log.debug("Main started")

    loop = asyncio.get_event_loop()
    # asyncio.set_event_loop(loop)

    log.info("About to schedule later")
    future = loop.call_later(0.5, do_something, "this is the msg")
    log.info("ok its scheduled")

    loop.run_until_complete(something_long(future))

    # log.critical("starting a long thing")
    # time.sleep(1.0)
    # log.critical("done with a long thing")

    # loop.run_forever()

    while True:
        time.sleep(0.2)
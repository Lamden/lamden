import asyncio, time
from cilantro.logger import get_logger

DELAY = 1.0

log = get_logger("Log")


def startup():
    log.info("im starting up")

def do_something(arg):
    log.info("doing something with arg: {}".format(arg))

def something_hella_long():
    delay = DELAY * 2
    log.info("Starting something hella long that will take {} seconds".format(delay))
    time.sleep(delay)
    log.info("done with that hella long thing")


def main():
    log.debug("main started")
    loop = asyncio.get_event_loop()

    startup()

    log.info("Calling do_something after {} seconds".format(DELAY))
    loop.call_later(DELAY, do_something, 'ay this dat arg')

    log.info("Starting a long running task")
    something_hella_long()
    log.info("Done with long running task")

    loop.run_forever()


if __name__== "__main__":
    main()


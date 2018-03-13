from cilantro.logger import get_logger
from cilantro.protocol.reactor import NetworkReactor, ReactorCore


def do_something(data):
    log = get_logger("Main")
    log.info("do_something with data: {}".format(data))

def do_something_else(data):
    log = get_logger("Main")
    log.info("do_something_ELSE with data: {}".format(data))

if __name__ == "__main__":
    log = get_logger("Main")
    log.debug("\n\n-- MAIN THREAD --")
    # q = aioprocessing.AioQueue()
    # reactor = NetworkReactor(queue=q)
    # reactor.start()
    #
    # q.coro_put(Command(Command.SUB, url=URL, callback=do_something))
    #
    # q.coro_put(Command(Command.PUB, url=URL2, data=b'oh boy i hope this gets through'))

    nr = NetworkReactor()
    nr.execute(Command.SUB, url=URL, callback=do_something)
    nr.execute(Command.PUB, url=URL2, data=b'oh boy i hope this gets through')

    log.critical("Will stop subbing in 6 seconds...")
    time.sleep(6)
    nr.execute(Command.UNSUB, url=URL)

    log.critical("Rescribing in 2 seconds...")
    time.sleep(2)
    nr.execute(Command.SUB, url=URL, callback=do_something_else)
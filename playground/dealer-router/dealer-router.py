import threading
import zmq


def config_router_dealer(context=None):
    context = context or zmq.Context.instance()
    sender = context.socket(zmq.DEALER)
    receiver = context.socket(zmq.ROU)


def step1(context=None):
    """Step 1"""
    print("doing step ONE with context ", context)
    context = context or zmq.Context.instance()
    # Signal downstream to step 2
    sender = context.socket(zmq.PAIR)
    sender.connect("inproc://step2")

    sender.send(b"")

def step2(context=None):
    """Step 2"""
    print("doing step TWO with context ", context)
    context = context or zmq.Context.instance()
    # Bind to inproc: endpoint, then start upstream thread
    receiver = context.socket(zmq.PAIR)
    print("step 2 binding to inproc://step2")
    receiver.bind("inproc://step2")

    thread = threading.Thread(target=step1)
    thread.start()

    # Wait for signal
    print("step 2 waiting for sig")
    msg = receiver.recv()

    # Signal downstream to step 3
    sender = context.socket(zmq.PAIR)
    print("step2 connecting to inproc://step3")
    sender.connect("inproc://step3")
    sender.send(b"")

def main():
    """ server routine """
    # Prepare our context and sockets
    context = zmq.Context.instance()

    # Bind to inproc: endpoint, then start upstream thread
    receiver = context.socket(zmq.PAIR)
    receiver.bind("inproc://step3")

    thread = threading.Thread(target=step2)
    thread.start()

    # Wait for signal
    print("main waiting for step3")
    string = receiver.recv()

    print("Test successful!")

    receiver.close()
    context.term()

if __name__ == "__main__":
    main()
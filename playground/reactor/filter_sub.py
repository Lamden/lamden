import zmq

def main():
    """ main method """

    # Prepare our context and publisher
    context    = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://localhost:5563")
    subscriber.connect("tcp://localhost:6000")
    subscriber.setsockopt(zmq.SUBSCRIBE, b"B")
    subscriber.setsockopt(zmq.SUBSCRIBE, b"C")

    count = 0
    while True:
        # Read envelope with filter
        count += 1
        print("Sub count: ", count)

        [address, contents] = subscriber.recv_multipart()
        print("[%s] %s" % (address, contents))

        if count == 20:
            print("\n\nUnsubscribing to secondary publisher\n\n")
            subscriber.disconnect("tcp://localhost:6000")

        if count == 40:
            print("\n\nResubscribing to secondary publisher\n\n")
            subscriber.connect("tcp://localhost:6000")

    # We never get here but clean up anyhow
    subscriber.close()
    context.term()

if __name__ == "__main__":
    main()
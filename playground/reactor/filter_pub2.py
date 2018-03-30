import time
import zmq

def main():
    """main method"""

    # Prepare our context and publisher
    context   = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.bind("tcp://*:6000")

    while True:
        # Write two messages, each with an envelope and content
        publisher.send_multipart([b"A", b"!!!! OTHER PUB -- We don't want to see this"])
        publisher.send_multipart([b"B", b"OTHER PUB -- We would like to see this"])
        publisher.send_multipart([b"C", b"OTHER PUB -- We would ALSO like to see this"])
        time.sleep(1)

    # We never get here but clean up anyhow
    publisher.close()
    context.term()

if __name__ == "__main__":
    print("Secondary pub started")
    main()
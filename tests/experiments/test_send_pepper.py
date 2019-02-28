import zmq
# host = 'tcp://delegate1.anarchynet.io'
host = 'tcp://13.57.9.49'
port = 10004

URL = "{}:{}".format(host, port)


def send_pepper():
    print("sending pepper")
    ctx = zmq.Context()
    sock = ctx.socket(zmq.DEALER)
    # sock = ctx.socket(zmq.ROUTER)
    print("connecting to URL {}".format(URL))
    sock.connect(URL)
    print("about to send multipart...")
    # sock.send_multipart([b'127.0.0.1', b'cilantro_ee_pepper'])
    sock.send_multipart([b'cilantro_ee_pepper'])
    print("done sending request, now waiting for reply")

    reply = sock.recv_multipart()
    print("got reply {}!!!!".format(reply))

    sock.send_multipart([b'127.0.0.1', b'cilantro_ee_pepper', b'A'*64])


if __name__ == '__main__':
    send_pepper()

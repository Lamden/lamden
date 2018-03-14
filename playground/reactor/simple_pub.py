import zmq
import asyncio
import time

URL = "tcp://127.0.0.1:5566"

class Pub():
    def __init__(self, url=URL):
        self.url = url
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(socket_type=zmq.PUB)
        self.socket.bind(self.url)

    def broadcast(self):
        for i in range(16):
            print("sending msg #{}".format(i))
            self.socket.send("hello #{}".format(i).encode())
            time.sleep(1)


if __name__ == "__main__":
    pub = Pub()

    print("Pub starting...")
    pub.broadcast()
    print("done")
import socket
import time

MSG_COUNT = 10000000
# MSG_COUNT = 100

CHECKPOINT = pow(2, 16)

UDP_IP = "127.0.0.1"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

start = time.time()
print("starting test with {} messages...".format(MSG_COUNT))


while MSG_COUNT > 0:
    # print("waiting for msg...")
    data, addr = sock.recvfrom(128)
    # print("received msg: {}".format(data))
    MSG_COUNT -= 1
    if MSG_COUNT % CHECKPOINT == 0:
        end = time.time()
        delta = end - start
        print("Checkpoint - {} msgs ... Time elapsed: {}".format(MSG_COUNT, delta))


end = time.time()
delta = end - start

print("Total runtime: {} seconds".format(delta))
print("Messages/second: {}".format(MSG_COUNT // delta))
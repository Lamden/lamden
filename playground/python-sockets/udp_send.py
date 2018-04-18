import socket
import time

MSG_COUNT = 10000000
# MSG_COUNT = 100

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
MSG = b"AY ITS YA BOY COMIN AT U LIKE OVER UDP!!!"


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.connect((UDP_IP, UDP_PORT))

time.sleep(1)
start = time.time()
print("starting test with {} messages...".format(MSG_COUNT))

while MSG_COUNT > 0:
    # print("Sending msg...")
    # sock.sendto(MSG, (UDP_IP, UDP_PORT))
    sock.send(MSG)
    # print("sent")
    MSG_COUNT -= 1
    # time.sleep(1)

end = time.time()
delta = end - start


print("Total runtime: {} seconds".format(delta))
print("Messages/second: {}".format(MSG_COUNT // delta))
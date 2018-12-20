from cilantro.logger import get_logger
import time, os


def get_mn_urls():
    if os.getenv('HOST_IP'):
        ips = os.getenv('MASTERNODE', '0.0.0.0')
        # Set _MN_URL to be a list of IPs if we are in multimaster setting
        if ',' in ips:
            ips = ips.split(',')
        else:
            ips = [ips]

        urls = ["http://{}:8080".format(ip) for ip in ips]
        return urls

    # If this is not getting run on a container, set MN URL to 0.0.0.0
    else:
        return ["http://0.0.0.0:8080"]


def countdown(duration: int, msg: str, log=None, status_update_freq=5):
    _l = log or get_logger("Countdown")
    if duration > status_update_freq:
        num_sleeps = duration // status_update_freq

        for _ in range(num_sleeps):
            time.sleep(status_update_freq)
            duration -= status_update_freq
            _l.important3(msg.format(duration))

    if duration > 0:
        time.sleep(duration)


def int_to_padded_bytes(i: int) -> bytes:
    SIZE = 32
    s = str(i)
    assert len(s) <= SIZE, "int {} is too long!".format(s)

    padding = SIZE - len(s)
    s = '0'*padding + s
    b = s.encode()

    assert len(b) == SIZE, "{} is not size {}".format(b, SIZE)

    return s.encode()
from cilantro_ee.core.logger import get_logger
import time

log = get_logger("MN_URL_GETTER")


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

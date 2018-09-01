import nacl
import nacl.encoding
import nacl.signing


def generate_keys(seed=None):
    if seed is not None:
        s = nacl.signing.SigningKey(seed=seed)
    else:
        s = nacl.signing.SigningKey.generate()
    v = s.verify_key
    return s, v


def get_vk(s):
    s, v = format_to_keys(s)
    s, v = keys_to_format(s, v)
    return v


def keys_to_format(s, v):
    s = s.encode()
    v = v.encode()
    return s.hex(), v.hex()


def format_to_keys(s):
    s = bytes.fromhex(s)
    s = nacl.signing.SigningKey(s)
    return s, s.verify_key


def new(seed=None):
    s, v = generate_keys(seed=seed)
    return keys_to_format(s, v)


def sign(s: str, msg: bytes):
    assert type(msg).__name__ == 'bytes', 'Message argument must be a byte string.'
    (s, v) = format_to_keys(s)
    return s.sign(msg).signature.hex()


def verify(v: str, msg, sig):
    v = bytes.fromhex(v)
    sig = bytes.fromhex(sig)
    v = nacl.signing.VerifyKey(v)
    try:
        v.verify(msg, sig)
    except nacl.exceptions.BadSignatureError:
        return False
    except Exception:
        return False
    return True

from zmq.utils import z85
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519
from lamden.logger.base import get_logger

def z85_key(key):
    bvk = bytes.fromhex(key)
    try:
        pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
    # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
    except RuntimeError:
        return
    except Exception as err:
        log = get_logger('Z85_KEY')
        log.error(f'Cannot convert {key} to z85. {err}')
        print(f'Cannot convert {key} to z85. {err}')

    return z85.encode(pk)
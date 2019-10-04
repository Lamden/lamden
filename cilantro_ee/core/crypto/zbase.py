import base64

zbase32_map = {
    'A': 'y', 'B': 'b', 'C': 'n', 'D': 'd', 'E': 'r', 'F': 'f', 'G': 'g', 'H': '8',
    'I': 'e', 'J': 'j', 'K': 'k', 'L': 'm', 'M': 'c', 'N': 'p', 'O': 'q', 'P': 'x',
    'Q': 'o', 'R': 't', 'S': '1', 'T': 'u', 'U': 'w', 'V': 'i', 'W': 's', 'X': 'z',
    'Y': 'a', 'Z': '3', '2': '4', '3': '5', '4': 'h', '5': '7', '6': '6', '7': '9',
    '=': '='
}

base32_map = {
    'y': 'A', 'b': 'B', 'n': 'C', 'd': 'D', 'r': 'E', 'f': 'F', 'g': 'G', '8': 'H',
    'e': 'I', 'j': 'J', 'k': 'K', 'm': 'L', 'c': 'M', 'p': 'N', 'q': 'O', 'x': 'P',
    'o': 'Q', 't': 'R', '1': 'S', 'u': 'T', 'w': 'U', 'i': 'V', 's': 'W', 'z': 'X',
    'a': 'Y', '3': 'Z', '4': '2', '5': '3', 'h': '4', '7': '5', '6': '6', '9': '7',
    '=': '='
}


def bytes_to_zbase32(b: bytes):
    b = base64.b32encode(b)
    b = b.decode()

    z = ''
    for bb in b:
        z += zbase32_map[bb]

    return z


def zbase32_to_bytes(z: str):
    b = ''
    for zz in z:
        b += base32_map[zz]

    b = b.encode()
    b = base64.b32decode(b)

    return b

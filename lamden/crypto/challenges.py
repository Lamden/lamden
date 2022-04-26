import random
import string
from lamden.crypto.wallet import verify

def create_challenge() -> str:
    return ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for _ in range(25))

def verify_challenge(peer_vk: str, challenge: str, challenge_response: str) -> bool:
    return verify(vk=peer_vk, msg=challenge, signature=challenge_response)
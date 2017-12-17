from ecdsa import SigningKey, VerifyingKey, NIST192p
import ecdsa
import hashlib

def generate_keys():
	# generates a tuple keypair
	s = SigningKey.generate()
	v = s.get_verifying_key()
	return s, v

def keys_to_format(s, v):
	# turns binary data into desired format
	s = s.to_string()
	v = v.to_string()
	return s.hex(), v.hex()

def format_to_keys(s):
	# returns the human readable format to bytes for processing
	s = bytes.fromhex(s)

	# and into the library specific object
	s = SigningKey.from_string(s, curve=NIST192p)
	v = s.get_verifying_key()
	return s, v

def new():
	# interface to creating a new wallet
	s, v = generate_keys()
	return keys_to_format(s, v)

def sign(s, msg):
	(s, v) = format_to_keys(s)
	signed_msg = s.sign(msg, hashfunc=hashlib.sha1, sigencode=ecdsa.util.sigencode_der)
	return signed_msg.hex()

def verify(v, msg, sig):
	v = bytes.fromhex(v)
	v = VerifyingKey.from_string(v, curve=NIST192p)
	try:
		return v.verify(bytes.fromhex(sig), msg, hashfunc=hashlib.sha1, sigdecode=ecdsa.util.sigdecode_der)
	except:
		return False
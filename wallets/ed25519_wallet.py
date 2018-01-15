import nacl
import nacl.encoding
import nacl.signing

def generate_keys():
	s = nacl.signing.SigningKey.generate()
	v = s.verify_key
	return (s, v)

def keys_to_format(s, v):
	s = s.encode()
	v = v.encode()
	return s.hex(), v.hex()

def format_to_keys(s):
	s = bytes.fromhex(s)
	s = nacl.signing.SigningKey(s)
	return s, s.verify_key

def new():
	s, v = generate_keys()
	return keys_to_format(s, v)

def sign(s, msg):
	(s, v) = format_to_keys(s)
	return s.sign(msg).hex()

def verify(v, msg, sig):
	v = bytes.fromhex(v)
	sig = bytes.fromhex(sig)
	v = nacl.signing.VerifyKey(v)
	try:
		v.verify(sig)
	except:
		return False
	return True
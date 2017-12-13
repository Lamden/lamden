from ecdsa import SigningKey, NIST192p

def generate_keys():
	# generates a tuple keypair
	s = SigningKey.generate()
	v = s.get_verifying_key()
	return (s, v)

def keys_to_format(s, v):
	# turns binary data into desired format
	s = s.to_string()
	v = v.to_string()
	return (s.hex(), v.hex())

def format_to_keys(s, v):
	# returns the human readable format to bytes for processing
	s = bytes.fromhex(s)
	v = bytes.fromhex(v)

	# and into the library specific object
	s = SigningKey.from_string(s, curve=NIST192p)
	v = s.get_verifying_key()
	return(s, v)

def new():
	# interface to creating a new wallet
	s, v = generate_keys()
	return keys_to_format(s, v)
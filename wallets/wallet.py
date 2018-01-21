def generate_keys():
	raise NotImplementedError

def keys_to_format(s, v):
	raise NotImplementedError

def format_to_keys(s):
	raise NotImplementedError

def new():
	raise NotImplementedError

def sign(s, msg):
	raise NotImplementedError

def verify(v, msg, sig):
	raise NotImplementedError

class WalletType(object):
	@staticmethod
	def generate_keys():
		raise NotImplementedError

	@staticmethod
	def keys_to_format(s, v):
		raise NotImplementedError

	@staticmethod
	def format_to_keys(s):
		raise NotImplementedError

	@staticmethod
	def new():
		raise NotImplementedError

	@staticmethod
	def sign(s, msg):
		raise NotImplementedError

	@staticmethod
	def verify(v, msg, sig):
		raise NotImplementedError
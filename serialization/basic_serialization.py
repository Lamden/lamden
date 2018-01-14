from transactions import basic_transaction as transaction

def serialize(t):
	#$<amount>[<from>]<to>)<proof>~<signature>
	s = '$'
	s += str(t['payload']['amount'])

	s += '['
	s += str(t['payload']['from'])

	s += ']'
	s += str(t['payload']['to'])

	s += ')'
	s += str(t['metadata']['proof'])

	s += '~'
	s += str(t['metadata']['signature'])
	
	return s

def deserialize(s):
	s = str(s)

	t = {
		'payload' : {
			'to' : None,
			'from' : None,
			'amount' : None
		},
		'metadata' : {
			'proof' : None,
			'signature' : None
		}
	}
	a = s.find('$')
	b = s.find('[')
	c = s.find(']')
	d = s.find(')')
	e = s.find('~')
	t['payload']['amount'] = s[a+1:b]
	t['payload']['from'] = s[b+1:c]
	t['payload']['to'] = s[c+1:d]
	t['metadata']['proof'] = s[d+1:e]
	t['metadata']['signature'] = s[e+1:]

	return t
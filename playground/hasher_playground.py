from cilantro.proofs.pow import SHA3POW, POW
import json
import requests

data = {"payload": {"to": "kevin", "amount": "900", "from": "davis", "type": "t"}, "metadata": {"sig": "0x123", "proof": "000000"}}
payload = data["payload"]

dict_in_bytes = str.encode(json.dumps(payload))

proof = SHA3POW.find(dict_in_bytes)

print(proof[0])

check = SHA3POW.check(dict_in_bytes, proof[0])

print(check)

data["metadata"]["proof"] = proof[0]

r = requests.post(url='http://127.0.0.1:7777', json=data)

import requests

requests.post('http://localhost:8080', b"""\x101P\x01\x01\x03$\x941\x01\x82\x0b\xff\x103@\x02Qh\x01\x02-@\x021\x05\x02\x021!\x8a\x03\xffc1f845ad\x158967b93092d59e4ef56aef3eba49c33079119b9c856a5354e9ccdf84import currency\ncurrency.transfer_coins('20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d', 358)\x00\x011\x05\x02\x011\x11\x02\x04\xffdef28daf\x13cdac38b9788b705a95b9c142522e9edaadfb3b2252becfcb74a57dbecbcd0a3bac29dc3f7c94adb052a2a77574c533c46d8f98c8682e69c2bceea80fa5a8e02b9d24b07800759681241e5a08
""")

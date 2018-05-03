# TODO -- write tests surrounding the dynamic creations of Constants.Testnet

"""
tests for:
- deterministic wallet key generation

- dynamic witness/delegate creation (Constants.Testnet.Delegates and Constants.Testnet.Witnesses)
- correct VK's to URL mapping in Constants.Testnet.AllNodes
- All this shoudl be tested for both reading witness/delegate config info from environment vars (which will happen when
we run on VM), as well as config.json (when we run with bootstrap.py).
Or are we even going to be using bootstrap.py anymore? Probs not.
"""
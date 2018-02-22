This describes spinning up a masternode + witness+ delegate, and how run test transaction through them.

## PREREQUISITES:
### Spin up databases
- Make sure mongo and redis are running in the background (run ```sudo mongod``` and ```redis-server``` in seperate terminal tabs)
```
## Spinning up instances
Open 3 separate terminal tabs, and spin up a masternode, delegate, witness in each.

### Masternode
```python
from cilantro.networking.masternode import Masternode
mn = Masternode()
mn.setup_web_server()
```
### Witness
```python
from cilantro.networking.witness import Witness
w = Witness()
w.start_async()
```

### Delegate
```python
from cilantro.networking.delegate import Delegate
d = Delegate()
d.start_async()
```

## Creating test transactions
With all 3 nodes up and running, you should now be able to send transactions as POST requests to masternode at the localhost:8080/ endpoint

Here are some utility methods for creating signed standard transactions. 
I recommend you just copy and paste them into a ipython terminal and invoke them ad-hoc.
The tuples STU/DENTON/DAVIS contain the (signing_key, verifying_key) for each of us, and we each have some funds seeded in the genesis block.

```python
from cilantro.wallets.ed25519 import ED25519Wallet
from cilantro.serialization.json_serializer import JSONSerializer
from cilantro.proofs.pow import SHA3POW

STU = ('24e90019ce7dbfe3f6e8bada161540e1330d8d51bff7e524bcd34b7fbefb0d9a260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f',
 '260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f')
DAVIS = ('d851136c3a2e0b93c929b184f75644d923a6c372bac7de1dc8a5353d07433123f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f',
 'f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f')
DENTON = ('b5c409614cf07f8d57c30da53bcccc62c7e7723e15298ed6fcace29af4a413245d3267ee2454ace1a845f39674f127a4b838cbd38027ec6686b13d374609d0fe',
          '5d3267ee2454ace1a845f39674f127a4b838cbd38027ec6686b13d374609d0fe')

def create_std_tx(sender: tuple, recipient: tuple, amount: float):
    """
    Utility method to create signed transaction
    :param sender: A tuple containing the (signing_key, verifying_key) of the sender
    :param recipient: A tuple containing the (signing_key, verifying_key) of the recipient
    :param amount: The amount to send
    :return:
    """
    tx = {"payload": ["t", sender[1], recipient[1], str(amount)], "metadata": {}}
    tx["metadata"]["proof"] = SHA3POW.find(JSONSerializer.serialize(tx["payload"]))[0]
    tx["metadata"]["signature"] = ED25519Wallet.sign(sender[0], JSONSerializer.serialize(tx["payload"]))
    return tx
```

To create a standard transaction from Stu to Davis for 10 dollars, you would call
```python
tx = create_std_tx(STU, DAVIS, 10)
```
Then just print the transaction and copy the dictionary to your clipboard

### Sending Transaction to Masternode

Now, either create a python request object and send this post data programatically, or more easily use Postman (or some other UI for sending post requests).
If you want to use the transaction you printed in a python terminal in Postman, you will have to convert all the single quotes to double quotes. To quickly do this, copy the transaction dictionary to your clipboard, open a terminal, and run:
```
echo `pbpaste` | sed "s/\'/\"/g" | `pbcopy`
```
And the transcation dictionary with double quotes will be copied to your clipboard.

Set the transaction dictionary in the transaction body (raw format), and send a POST request to http://127.0.0.1:8080/ and it should go through the system.

## Viewing Results

### Delegate State
Delegate keeps track of the real-time state of balances using Redis. Much of the output can be seen in terminals running masternode/witness/delegate. To check out the scratch state and transaction queue, here are some helper methods.
I just recommend you just copy/paste them into an ipython terminal.
```python
import redis
from cilantro.db.constants import *
import json
from cilantro.wallets.ed25519 import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
from cilantro.serialization.json_serializer import JSONSerializer

r = redis.StrictRedis(host='localhost', port=6379, db=0)

BALANCE_KEY = 'BALANCE'
SCRATCH_KEY = 'SCRATCH'
QUEUE_KEY = 'QUEUE'
TRANSACTION_KEY = 'TRANSACTION'

def encode_tx(tx):
    return json.dumps(tx).encode()

def flush_scratch():
    print('flushing scratch...')
    for key in r.hscan_iter(SCRATCH_KEY):
        r.hdel(SCRATCH_KEY, key[0])

def flush_queue():
    print('flushing queue...')
    queue_len = r.llen(QUEUE_KEY)
    for _ in range(queue_len):
        r.lpop(QUEUE_KEY)

def flush_transactions():
    print('flushing transactions...')
    for key in r.hscan_iter(TRANSACTION_KEY):
        r.hdel(TRANSACTION_KEY, key[0])
        
def print_balance():
    for person, balance in r.hgetall(BALANCE_KEY).items():
        print("{} : {}".format(person, balance))
        
def print_scratch():
    for person, balance in r.hgetall(SCRATCH_KEY).items():
        print("{} : {}".format(person, balance))
        
def print_queue():
    queue_len = r.llen(QUEUE_KEY)
    for x in r.lrange(QUEUE_KEY, 0, queue_len):
        print(x)
        
def print_status():
    print('-----------------------------------')
    print('BALANCES')
    print_balance()
    print('-----------------------------------')
    print('SCRATCH')
    print_scratch()
    print('-----------------------------------')
    print('QUEUE')
    print_queue()
    print('-----------------------------------\n')
```

To look at the scratch run
```
print_scratch()
```
and to look at the balance run
```
print_balance()
```
ect, ect.

It may be wise to clear the scratch inbetween tests, using
```
flush_scratch()
```

To check out the cold storage, you would have to just open a Mongo CLI and run command on the cilantro db. (I haven't written a python wrapper for this yet, but you can checkout the code in blockchain_driver.py if you want to look at the cold storage using python)

### Cold Storage (Masternode)
Masternode holds the entire blockchain, as well as a dictionary of the latest balances. To view this data, use the Mongo CLI.
First open a new tab in terminal, and run ```mongo``` to start the CLI.
Then run:
```
use cilantro
```
To select the cilantro database. You can now use the commands below to view the blockchain and latest balances.

#### To view the entire blockchain:
```
db['blockchain'].find({}).pretty()
```
#### To view the balances:
```
db['balances'].find({}).pretty()
```

### Example Signed Transaction 
A signed transaction from Stu to Davis for 4 coin:
```
{"metadata": {"proof": "7b707d7e1c92fdf7a0195852f26346d3",
  "signature": "fdb7a1d9dd34121e4005c8cb9dcfcd0217d9245158dfad71dbea0538fcdb23a43ac0c952263ed08d966d8db1d1d655b3178edf14ba91a35ff52b44dec8807b0f"},
 "payload": ["t",
  "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
  "f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f",
  "4"]}
```






i like turtles


This describes spinning up a masternode + witness+ delegate, and how run test transaction through them.

## PREREQUISITES:
### Spin up databases
- Make sure mongo and redis are running in the background (run ```sudo mongod``` and ```redis-server``` in seperate terminal tabs)
### Set balances in redis
In reality, this would be done by the delegates querying masternode for the latest state when they boot up, but for now it has to be done manually. In a python terminal, run this:
```python
import redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)
BALANCE_KEY = 'BALANCE'
STU = ('373ac0ec93038e4235c4716183afe55dab95f5d780415f60e7dd5363a2d2fd10',
       '403619540f4dfadc2da892c8d37bf243cd8d5a8e6665bc615f6112f0c93a3b09')
DAVIS = ('1f4be9265694ec059e11299ab9a5edce314f28accab38e09d770af36b1edaa27',
         '6fbc02647179786c10703f7fb82e625c05ede8787f5eeff84c5d9be03ff59ce8')
DENTON = ('c139bb396b4f7aa0bea43098a52bd89e411ef31dccd1497f4d27da5f63c53b49',
          'a86f22eabd53ea84b04e643361bd59b3c7b721b474b986ab29be10af6bcc0af1')

r.hset(BALANCE_KEY, STU[1], 1000)
r.hset(BALANCE_KEY, DAVIS[1], 500)
r.hset(BALANCE_KEY, DENTON[1], 750)
```

## Spinning up instances
Open 3 separate terminal tabs, and spin up a masternode, delegate, witness in each.

### Masternode
```python
from cilantro.networking.masternode import Masternode
from aiohttp import web

node = Masternode()
app = web.Application()

app.router.add_post('/', node.process_request)
app.router.add_post('/add_block', node.process_block_request)
web.run_app(app, host="127.0.0.1", port=int(node.external_port))
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
import json
from cilantro.wallets.ed25519 import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
from cilantro.serialization.json_serializer import JSONSerializer

def create_std_tx(sender: tuple, recipient: tuple, amount: float):
    """
    Utility method to create signed transaction
    :param sender: A tuple containing the (signing_key, verifying_key) of the sender
    :param recipient: A tuple containing the (signing_key, verifying_key) of the recipient
    :param amount: The amount to send
    :return: The transaction as a dictionary
    """
    tx = {"payload": {"to": recipient[1], "amount": str(amount), "from": sender[1], "type":"t"}, "metadata": {}}
    # tx["metadata"]["proof"] = SHA3POW.find(json.dumps(tx["payload"]).encode())[0]
    tx["metadata"]["proof"] = SHA3POW.find(JSONSerializer.serialize(tx["payload"]))[0]
    tx["metadata"]["signature"] = ED25519Wallet.sign(sender[0], json.dumps(tx["payload"]).encode())
    return tx
    
STU = ('373ac0ec93038e4235c4716183afe55dab95f5d780415f60e7dd5363a2d2fd10',
       '403619540f4dfadc2da892c8d37bf243cd8d5a8e6665bc615f6112f0c93a3b09')
DAVIS = ('1f4be9265694ec059e11299ab9a5edce314f28accab38e09d770af36b1edaa27',
         '6fbc02647179786c10703f7fb82e625c05ede8787f5eeff84c5d9be03ff59ce8')
DENTON = ('c139bb396b4f7aa0bea43098a52bd89e411ef31dccd1497f4d27da5f63c53b49',
          'a86f22eabd53ea84b04e643361bd59b3c7b721b474b986ab29be10af6bcc0af1')
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
A signed transaction from Stu to Davis for 10 coin:
```
{"metadata": {"proof": "eca5be799af673635fab49bddbb2c4c0", "signature": "16b42ba1ebb5f6be0e90da12c4a282e38ce9b3c857d78e3842082ffcfa52e7041266549a5946daee82777fb71a17bbb000b765c38c3efd9913178c93912fd7077b22746f223a202236666263303236343731373937383663313037303366376662383265363235633035656465383738376635656566663834633564396265303366663539636538222c2022616d6f756e74223a2022313030222c202266726f6d223a202234303336313935343066346466616463326461383932633864333762663234336364386435613865363636356263363135663631313266306339336133623039222c202274797065223a202274227d"}, "payload": {"amount": "100", "from": "403619540f4dfadc2da892c8d37bf243cd8d5a8e6665bc615f6112f0c93a3b09", "to": "6fbc02647179786c10703f7fb82e625c05ede8787f5eeff84c5d9be03ff59ce8", "type": "t"}}
```

A signed transaction from Davis to Denton for 5 coin:
```
{"metadata": {"proof": "4e498a4781733a6219efdaaf751fa9eb", "signature": "3497b98126d5c6a6cf3a891b2626f89656e0231a08eefbd71e7da88f6a093388216bbe0c514326976f5cac28379c9dcfd171a2552f295f5280fe0bc43c3b100c7b22746f223a202261383666323265616264353365613834623034653634333336316264353962336337623732316234373462393836616232396265313061663662636330616631222c2022616d6f756e74223a202235222c202266726f6d223a202236666263303236343731373937383663313037303366376662383265363235633035656465383738376635656566663834633564396265303366663539636538222c202274797065223a202274227d"}, "payload": {"amount": "5", "from": "6fbc02647179786c10703f7fb82e625c05ede8787f5eeff84c5d9be03ff59ce8", "to": "a86f22eabd53ea84b04e643361bd59b3c7b721b474b986ab29be10af6bcc0af1", "type": "t"}}
```

### Example Postman Transaction 
![alt text](https://i.imgur.com/dMGVYaG.png "Examples Postman Request")






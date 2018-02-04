# Cilantro

Cilantro is an enterprise level blockchain that is focused on high throughput and scalibility. Cilantro can process
1000s of tx/second and also incorporates a smart contract language called Seneca to provide additional functionality.
Additional features such as staking and anti-spam measures are also included out of the box.

## Technical Details

Cilantro is built utilizing the excellent ZeroMQ messaging platform. ZMQ is highly respected networking library that
provides advanced socket functionality and several useful message patterns that work well in an asynchronous framework.
The Cilantro network consists of three key network participants: the masternodes, the witnesses, and the delegates.
Each of these are integral to the network and are described in detail below.

### Masternodes
Masternodes serve as the entry point into the Cilantro network and publish transactions sent from individual nodes on
the network. Masternodes are crucial security actors and stake 10,000+ TAU in order to obtain masternode status. They
are inherently altruistic and providing a service in order for the blockchain to provide such high throughput. They also
support the cold storage of the transaction database once consumption is done by the network. They have no say as to what is 'right,'
as governance is ultimately up to the network. However, they can monitor the behavior of nodes and tell the network who is misbehaving.

### Witnesses
Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
transactions that include stake reserves being spent by users staking on the network.

### Delegates
Delegates bundle up transactions into blocks and are rewarded with TAU for their actions. They receive approved transactions
from delegates and broadcast blocks based on a 1 second or 10,000 transaction limit per block. They also act as executors
of the smart contracts passed along in transactions and are critical to the Cilantro security model.


```
Give examples
```

## Installing


# Cilantro

[![Coverage Status](https://coveralls.io/repos/github/Lamden/cilantro/badge.svg?branch=master)](https://coveralls.io/github/Lamden/cilantro?branch=master)

Cilantro is a piece of software that allows the modular construction of blockchains. It is the piece of the puzzle that allows rapid development of decentralized systems while not restricting the possibilities of what said system can do. Lamden’s main deployment of Cilantro is for atomic swaps via the Clove protocol. This deployment is what holds the Lamden Tau coin and is what our first decentralized application will be for the public.

What this deployment serves is two purposes: one, provide free and fast transactions and atomic swaps to introduce true interoperability to the crypto space in a way that is not controlled by a singular party, and two, demonstrate a successful deployment of the Lamden suite to create a brand new blockchain application.




## Technical Details
Cilantro is an enterprise level blockchain that is focused on high throughput and scalability. Cilantro can process
thousands of transactions per second and incorporates a smart contract language called Seneca to provide advanced user functionality. Features such as staking and anti-spam measures are also included out of the box.


Cilantro is built utilizing the ZeroMQ messaging platform. ZMQ is respected networking library that
provides advanced socket functionality and several useful message patterns that work well in an asynchronous framework.
The Cilantro network consists of individuals transacting on the network alongside three key types of participants: the masternodes, the witnesses, and the delegates.
Each of these three are integral to the network and are described in more detail below.

### Masternodes
Masternodes serve as the entry point into the Cilantro network and publish transactions sent from individual nodes on
the network. Masternodes are crucial security actors and stake 100,000+ TAU in order to obtain masternode status. They
are inherently altruistic and providing a service in order for the blockchain to provide such high throughput. They also
support the cold storage of the transaction database once consumption is done by the network. They have no say as to what is 'right,'
as governance is ultimately up to the network. However, they can monitor the behavior of nodes and tell the network who is misbehaving.

### Witnesses
Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
transactions that include stake reserves being spent by users staking on the network. They vote on which delegates
will makeup the set of validators at a point in time.

### Delegates
Delegates bundle up transactions into blocks and are rewarded with TAU for their actions. They receive approved transactions
from delegates and broadcast blocks based on a 1 second or 10,000 transaction limit per block. A group of delegates exchange 
signed merkle hashes of transactions in order to establish consensus. They also act as executors of the smart contracts 
passed along in non-standard transactions and are critical to the Cilantro security model.


## Installing
Cilantro is in a very activate state of development so be sure to pull often ;)

Highly recommended to be in an 3.6+ Python environment to ensure all dependencies play nice.  Also be sure to run cilantro
in a separate virtual environment to not affect other Python builds on your machine. 

Currently supported on Linux and macOS. Some dependencies are not available on Windows but Windows support will come in the near future.

    git clone https://github.com/Lamden/cilantro.git
    cd/to/cilantro
    pip3 install -r requirements.txt
    mkdir logs

Now you're all set to get up and running! Poke around and have some fun. 


## Testnet
https://testnet.lamden.io/


## API Documentation


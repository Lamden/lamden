"""
All nodes behavior "independently", meaning under no DIRECT control over others.
All nodes behave an act entirely as a function of their inputs

let A be the action space for a node.
let M be the possible input (messages) a node can receive
Let S be the current state of a node
let d(M, S) be a decision function that maps input to the action space, i.e. d(...) -> A

 In practice, M represents the possible messages (model types)
 d(..) represents the implementation logic for nodes.
 The action space, A, represents
    - possible updates to state, be it internal python object states, or MyRocks db states
    - output to other nodes, ie. d(M) results in a message being sent to another node
 Thus does it make sense to provide decorators to allow
 nodes to easily define this d(X) for each X?

For n nodes, there are n^2 possible message sender,receiver combinations
i.e. masternode --> witness, masternode --> masternode, ...
And n for each node
- Do we need to consider situations where the same 'kind' of message gets
sent from two diferent nodes? Like could masternode receive the same 'kind' of
message from a delegate or a witness?
Seems like an edge cast

modify metatype of all node classes to allow implementor to use decorators for
handling message events

@recv(witness/transaction_msg)
def handle_tx_msg(self, msg):
    ...

@recv(delegate/blocksignature)
def handle_block_sig(self, msg):
    ...

and we could auto parse the thing into the appropriate model object for the callback

This could make 3rd party development super ez cuz all they have to do its define their
own model types, and this all magically gets just hooked into the callback decorators in
each node. So  you, as a 3rd party developer, would just have to do it create your own
model and then implement the defining behaviors.

Now, how to manage message sending? And how to manage sending/receiver from different URLS? Different
message types?
How to manager routing? Finger tables? Static routing table? Can we automate how this gets updated/reqeusted/ect
between nodes? Or at the least, abstract this into a new


In regards to reactor, can we self-contain it in its own class (passing the parent thread
as well as the parent), and just run the a method on the class to start the event loop?
(or have this happen at the end of its init)

In regards to messages...
Can we just dynamically register each ModelBase instances in a metaclass
And then how does a node parse a message into the correct subclass when it receives a message?


Can we have a metatype for nodes to make them behavior unpredictably? I.e. hijack all network calls and
make them behave nondeterministically somehow

Use signature object to enforce kwaargs

Descriptors to automate validation of model params





You might say, Davis, this is so abstract. Why are you thinking so hard about how to break things up into one million
pieces using abstraction and metaprogramming and such instead of just hamming down and building the MVP asap no rocky.

Consider this.
- Say a given node N can respond to |M| possible message types, and has |Q| possible states.
- Then it follows that there are |M|*|Q| possible situations a node can receive a message,
  meaning there are |M|*|Q| possible actions a node can perform (|A| = |M|*|Q|)
- Thus we must write |A| decision functions for all possible states and inputs.
- Of course in practice, many of these action will be the same. For example when a delegate receives a transaction from
  a witness it will likely behave the same in all states except when its actively interpreting.
  But this illustrates non the less that there is a very wide space of possible node inputs and outputs that could
  be very tricky to manage if a strong framework is not in place.
"""
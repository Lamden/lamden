# Consensus

## Basic Details
    Step 0) Delegate receives "POW-verified" tx from witness and interprets it to make sure tx is valid. If so add to Queue   
    Step 1) Delegate pops 10k transactions (stamps, atomic transactions, etc) from Queue into a block
    Step 2) Serialize block
    Step 2) Hash block object in order to generate unique block fingerprint 
    Step 3) **CONSENSUS**
    Step 4) Confirmed block is sent back to masternode for cold storage
    Step 5) Rewards
    Step 6) Process repeats (Step 1)
    
### What is Step 3?
Each of the 32 delegates will act as a state machine or deterministic Markov chain when it comes to consensus. There
will be states such as "performing consensus" and "in consensus" that each delegate can move between. Each delegate
keeps track of each other's state (2^5 total bits). Each delegate keeps track of how many other delegates return 
"in consensus" states based on how many match each other's hash of the latest block. The first delegate to see a 51%
"in consensus" state tally goes to Masternode and states consensus is achieved for this block. In this 
way we have achieved a quorum in a decentralized fashion. 

It's important to point out that while only 32 delegates will vote on particular block there will be 32 more "bench"
delegates that can step in if one goes offline. This leaves a pool of 64 delegates activate at any point in time. Every 
X blocks (say 100,000) an election is held and delegates are voted in/out. 

## How's the first implementation look like?
    REQ REP message pattern between all 32 delegates based on known IP addresses

Build, break, iterate, repeat.
    

## But what if there's no consensus?
Good question. We are actively researching this topic since more trivial solutions (ie longest chain rule) doesn't work 
well with our architecture. Some partial solutions are to hold elections for delegates more
frequently if the protocol has a hard time achieving consensus (to kick off bad actors or slow delegates) or taking only
the union between all block sets any time consensus is not achieved. These are not fully fleshed out and in
testnet builds we may just drop transactions out of blocks into a mempool and try to get consensus on subsequent blocks.
TBD. 


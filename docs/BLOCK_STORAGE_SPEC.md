# Blockchain Schema Spec

## Overview

This document describes the schema for how Cilantro stores blocks. Each block
consists of 2 parts:
1. **Block Hash**
  - The hash of this block's data
2. **Block Data**
  - A key-value store containing both required and optional metadata about this block.

Below is a diagram detailing the properties of blocks and how they are linked together.
![Blockchain Spec Diagram](https://www.lucidchart.com/publicSegments/view/f375769e-b275-450e-93ad-46a3212dcf7b/image.png)

## Individual Block Schema

### Block Data

The block data is essentially a key-value mapping, which can store any metadata
about the block. It can be customized to hold any key-values.

**Required block data fields** include:
*  **Previous Block Hash**
  - The previous block hash is simply the block hash of the previous block. This
    links blocks together
*  **Merkle Leaves**
  - The leaves of the merkle tree which are SHA3 hashes. All these leaves are then
    concatenated together into a string and stored in this value. To parse,
    clients must split the string every 64 characters to get the individual leaves.
    Nodes store the actual transaction data in a separate table.
*  **Merkle Root**
  - The Merkle root, a 64 hex character hash value.
*  **Block Contender**
  - The block contender is the original [Block Contender](https://github.com/Lamden/cilantro_ee/blob/master/cilantro_ee/messages/consensus/block_contender.py) object that ultimately
    was built into this block. It contains a list of signatures from the delegates
    who signed the block.

Additionally, developers can specify any arbitrary **optional key-values**. The default
configuration of Cilantro includes:
* **Timestamp**
  - The time the block was published by a Masternode, represented a unix epoch
    integer
* **Masternode Signature**
  - A signature of the Masternode who published this block (specifically, the Masternode signs this block's merkle root)

### Block Hash

The block hash is computed by sorting the block data lexigraphically by key,
concatenating their binary values, and then SHA3 hashing this concatenated binary.

For example, the lexigraphically sorted block data keys in Cilantro's default
configuration is
```
['block_contender',
 'masternode_signature',
 'merkle_leaves',
 'merkle_root',
 'prev_block_hash',
 'timestamp']
```
So to compute the block hash we would first compute the concatenated binary, as demonstarted below.
The block hash is then the SHA3 hash of this concatenated value. Notice how we are adding the
block data binaries together in lexigraphical order sorted by their keys.
```
concatenated binary = block contender binary + masternode signature binary + ... + timestamp binary

block hash = SHA3(concatenated binary)
```

## Genesis Block & Seeding Default Values

Unlike Bitcoin and Ethereum, Cilantro doesn't really have anything directly analogous to a Genesis block. This is because **all transactions in Cilantro are smart contracts**, including standard currency transactions, atomic swaps, votes, ect. Thus seeding any default values is actually done in the smart contracts themselves. For example, to seed any 'genesis wallets', developers specify a list of wallets and intial values in the implement of the standard [currency.seneca smart contract](https://github.com/Lamden/cilantro_ee/blob/master/cilantro_ee/contracts/lib/currency.seneca).

Since Cilantro does not use a 'genesis block' to seed default values, the 'literal genesis block'
exists simply as a placeholder for the first real block to be built. It is created
with a block hash of 0 and all block data fields set to 0 or None. Furthermore, because Cilantro uses smart contracts to implement both core transactions (such as currency/voting) and 3rd party transactions, the only significant configuration to be done in regards to seeding default values is the specification
of which default 'genesis' contracts should included in the initial deployment of
the blockchain. Currently the system will load all contracts in the cilantro_ee/contracts/lib folder.

## Table Schema
TODO

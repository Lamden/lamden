General description
===================
* A language to describe operations on the db
* Contract language should be easy to read and write, and should be intelligible for non-technical users, e.g. it shouldn't look like Lisp or Haskell.
* The most important capability is modeling organizations and access control
* Contracts are stored in a blockchain
* By traversing the entire blockchain and sequentially running all the operations described in the contracts, db state can be derived.
* Contracts can reference other contracts in the blockchain, with some limitation on depth for system stability
* Contracts can reference data in the db
* Contracts are not Turing complete.
  * They'll have a fixed set of functions, will not flow control, e.g. loops.

Technical details
==================
* Contracts should be idempotent
  * e.g. we'll never have balance = balance - 10, it will be balance = 80.
  * I'm wondering a couple of things
    * Stu, do I have this right?
    * This would preclude certain edits to data when the creator of the contract isn't allowed to read the data he/she's editing.
      * Something like, I can vote for the managers of my retirement fund, I have one vote allocated to me every year, but when I cast my vote, they don't want me to see running totals for the candidates, so I only can say +1.
* Constraints
  * There will be rules that validate smart contracts
  * The rules themselves will be smart contracts
* Contracts will have publicly viewable fields and private sections
  * Can the private sections manipulate data? If so how do we ensure the db nodes have the key to view them?
* Contracts will have a size limit
* Contract submission requires a proof-of-work
  * The system may tax larger contracts by requiring a more difficult hashing problem, (i.e. more leading zeros in hash)
* We should have key inheritance with the ability to model RBAC

* How requests are processed
  * requests -> delegates -> transform into raw operations -> run consensus

Style
  really legible
  ultimately going to be a Cassandra query
  but it should boil down into a meta query
  checks handled by delegates

User Stories
============
* I should be able to implement basic banking rules as one or more smart contracts e.g.
  * Tokens removed from one wallet must be placed in one or more other wallets, and all transactions must sum to zero
  * A contract that removes tokens from a wallet must be signed by the wallet owner
* I want to restrict creation of permissions rules for my Db to users with a keypair with cert signed by key xyz.
* To access a patient's record, you must be a doctor assigned to the patient, or be the attending physician of a resident assigned to the patient

Comparable languages and inspiration
====================================
* Quill
* CQL
* SQL
* YAML
* Stu, I think you mentioned Q, is that right? Is this the one?
  https://en.wikipedia.org/wiki/Q_(programming_language_from_Kx_Systems)

Other Stuff
===========
* https://people.csail.mit.edu/gregs/ll1-discuss-archive-html/msg04323.html

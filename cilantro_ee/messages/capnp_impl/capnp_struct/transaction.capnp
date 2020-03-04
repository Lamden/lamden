@0x921d030365beff8c;

using V = import "values.capnp";

struct Delta {
    key @0 :Data;
    value @1 :Data;
}

struct MetaData {
    signature @0 :Data;
    timestamp @1 :Float32;
}

struct TransactionPayload {
    sender @0 :Data;
    processor @1: Data;
    nonce @2 :UInt64;

    stampsSupplied @3 :UInt64;

    contractName @4 :Text;
    functionName @5 :Text;
    kwargs @6 :V.Map(Text, V.Value);
}

struct Transaction {
    metadata @0: MetaData;
    payload @1: TransactionPayload;
}

struct TransactionData {
    hash @0: Data;
    transaction @1 :NewTransaction;
    status @2: UInt8;
    state @3: List(Delta);
    stampsUsed @4: UInt64;
}

struct Transactions {
    transactions @0 :List(Transaction);
}

struct TransactionBatch {
    transactions @0 :List(NewTransaction);
    timestamp @1: Float64;
    signature @2: Data;
    sender @3: Data;
    inputHash @4: Data;  # hash of transactions + timestamp
}

struct NewTransactionPayload {
    sender @0 :Data;
    processor @1: Data;
    nonce @2 :UInt64;

    stampsSupplied @3 :UInt64;

    contractName @4 :Text;
    functionName @5 :Text;
    kwargs @6 :Data;
}

struct NewTransaction {
    metadata @0: MetaData;
    payload @1: NewTransactionPayload;
}
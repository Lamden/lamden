@0x921d030365beff8c;

using V = import "values.capnp";

struct MetaData {
    proof @0 :Data;
    signature @1 :Data;
    timestamp @2 :Float32;
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
    transaction @0 :Transaction;
    status @1: Text;
    state @2: Text;
    contractType @3: UInt16;
}

struct Transactions {
    transactions @0 :List(Transaction);
}

struct TransactionBatch {
    transactions @0 :List(Transaction);
    timestamp @1: Float64;
    signature @2: Data;
    sender @3: Data;
    inputHash @4: Data;  # hash of transactions + timestamp
}

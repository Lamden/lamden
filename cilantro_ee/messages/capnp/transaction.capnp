@0x921d030365beff8c;

using V = import "values.capnp";

struct MetaData {
    proof @0 :Data;
    signature @1 :Data;
    timestamp @2 :Float32;
}

struct ContractPayload {
    sender @0 :Text;
    nonce @1 :Text;
    stampsSupplied @2 :UInt64;

    contractName @3 :Text;
    functionName @4 :Text;
    kwargs @5 :V.Map(Text, V.Value);
}

struct ContractTransaction {
    metadata @0: MetaData;
    payload @1: Data;
}
struct TransactionData {
    transaction @0 :Data;
    status @1: Text;
    state @2: Text;
    contractType @3: UInt16;
}

struct Transactions {
    transactions @0 :List(Data);
}

struct TransactionBatch {
    transactions @0 :List(Data);
    timestamp @1: Float32;
    signature @2: Data;
    sender @3: Data;
}

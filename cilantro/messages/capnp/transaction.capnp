@0x8cff3844f3101ec9;

struct MetaData {
    proof @0 :Data;
    signature @1 :Data;
    timestamp @2 :Float32;
}

struct ContractTransaction {
    metadata @0: MetaData;
    payload @1: Payload;
    contractName @2 :Data;

    struct Payload {
        sender @0 :Data;
        code @1 :Text;
        gasSupplied @2 :UInt32;
    }
}

struct TransactionData {
    contractTransaction @0 :ContractTransaction;
    status @1: UInt8;
    state @2: Text;
}

struct Transactions {
    transactions @0 :List(Data);
}

struct TransactionContainer {
    type @0 :UInt32;
    payload @1 :Data;
}

struct OrderingContainer {
    type @0 :UInt32;
    transaction @1 :Data;
    masternodeVk @2 :Data;
    utcTimeMs @3 :UInt64;
}

struct TransactionBatch {
    transactions @0 :List(OrderingContainer);
}

struct StandardTransaction {
    metadata @0 :MetaData;
    payload @1 :Payload;

    struct Payload {
        sender @0 :Data;
        receiver @1 :Data;
        amount @2 :UInt64;
    }
}

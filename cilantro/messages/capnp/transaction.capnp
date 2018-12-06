@0x8cff3844f3101ec9;

using V = import "values.capnp";


struct MetaData {
    proof @0 :Data;
    signature @1 :Data;
    timestamp @2 :Float32;
}


struct ContractTransaction {
    metadata @0: MetaData;
    payload @1: Payload;

    struct Payload {
        sender @0 :Data;
        contractName @1 :Text;
        functionName @2 :Text;
        stampsSupplied @3 :UInt64;
        nonce @4 :Text;
        kwargs @5 :V.Map(Text, V.Value);
    }
}


struct PublishTransaction {
    metadata @0: MetaData;
    payload @1: Payload;

    struct Payload {
        sender @0 :Data;
        contractName @1 :Text;
        contractCode @2 :Text;
        stampsSupplied @3 :UInt64;
        nonce @4 :Text;
    }
}


struct TransactionData {
    contractTransaction @0 :ContractTransaction;
    status @1: Text;
    state @2: Text;
    contractType @3: UInt16;
}


struct Transactions {
    transactions @0 :List(Data);
}


struct TransactionContainer {
    type @0 :UInt16;
    payload @1 :Data;
}


struct OrderingContainer {
    type @0 :UInt16;
    transaction @1 :Data;
    utcTimeMs @2 :UInt64;
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

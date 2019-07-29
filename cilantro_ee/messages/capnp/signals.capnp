@0xc8e348aff0c0e620;


struct Signal {
    messageType @0 :UInt32;
}

struct ExternalSignal {
    id @0 :UInt32;
    timestamp @1: Float32;
    sender @2: Data;
    signature @3: Data;
}
@0xc8e348aff0c0e620;


struct Signal {
    messageType @0 :UInt32;
}

struct ExternalSignal {
    id @0 :UInt32;
    timestamp @1: UInt32;
    sender @2: Data;
    signature @3: Data;
}

struct ExternalMessage {
    data @0 :Data;
    sender @1: Data;
    signature @2: Data;
}
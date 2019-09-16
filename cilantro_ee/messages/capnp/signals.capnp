@0xc8e348aff0c0e620;

# this file can go away completely
# ExternalMessage is signedMessage and ExternalSignal is signed signal
# signal is nothing but the messageType??

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

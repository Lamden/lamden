@0x93eca3fe49376df5;

struct Seal {
    signature @0: Data;
    verifyingKey @1: Data;
}

struct MessageMeta {
    type @0 :UInt16;
    uuid @1: UInt32;
    timestamp @2: Text;
    sender @3: Text;
}

struct Envelope {
    seal @0: Seal;
    meta @1: MessageMeta;
    message @2: Data;
}

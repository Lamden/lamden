@0x93eca3fe49376df5;

struct Envelope {
    type @0 :UInt16;
    uuid @1: UInt32;
    signature @2: Data;
    payload @3 :Data;
}
@0xc8e348aff0c0e620;

struct SignedMessage {
    msgType @0 :Data;
    message @1 :Data;
    signature @2: Data;
    signee @3: Data;
    timestamp @4: Float64;
}

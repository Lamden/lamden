@0x8cff3844f3101ec9;

struct MetaData {
    proof @0 :Data;
    signature @1 :Data;
    nonce @2 :Data;
    timestamp @3 :Float32;
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

struct VoteTransaction {
    metadata @0 :MetaData;
    payload @1 :Payload;

    struct Payload {
        sender @0 :Data;
        policy @1 :Data;
        choice @2 :Data;
    }
}

struct SwapTransaction {
    metadata @0 :MetaData;
    payload @1 :Payload;

    struct Payload {
        sender @0 :Data;
        receiver @1 :Data;
        amount @2 :UInt64;
        hashlock @3 :Data;
        expiration @4 :UInt64;
    }
}

struct RedeemTransaction {
    metadata @0 :MetaData;
    payload @1 :Payload;

    struct Payload {
        sender @0 :Data;
        secret @1 :Data;
    }
}

struct StampTransaction {
    metadata @0 :MetaData;
    payload @1 :Payload;

    struct Payload {
        sender @0 :Data;
        amount @1 :Int64;
    }
}

struct ElectionTransaction {
    enum Method {
      initiate @0;
      finalize @1;
    }

    metadata @0 :MetaData;
    payload @1 :Payload;

    struct Payload {
        sender @0 :Data;
        policy @1 :Data;
        method @2 :Method;
    }
}
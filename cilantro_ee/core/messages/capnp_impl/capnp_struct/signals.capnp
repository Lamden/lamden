@0xdf5825258a6a807b;

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

struct SignedMessage {
    msgType @0 :UInt16;
    message @1 :Data;
    signature @2: Data;
    signee @3: Data;
    timestamp @4: Float64;
}

struct BadRequest {
    timestamp @0 :UInt32;
}

struct BlockDataRequest {
    blockNum @0: UInt32;
}

struct LatestBlockHeightRequest {
    timestamp @0: UInt64;
}

struct LatestBlockHeightReply {
    blockHeight @0: UInt32;
}

struct LatestBlockHashRequest {
    timestamp @0: UInt64;
}

struct LatestBlockHashReply {
    blockHash @0: Data;
}

struct IPForVKRequest {
    vk @0: Data;
}

struct IPForVKReply {
    ip @0: Data;
}

struct Acknowledged {
    timestamp @0 :UInt32;
}

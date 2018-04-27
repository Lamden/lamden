@0x8a9fc3aa86af6ad8;


using import "envelope.capnp".Envelope;


struct ReactorCommand {
    envelope :union {
        unset @0 :Void;
        data @1 :Data;
    }

    kwargs @2 :List(Entry);
    struct Entry {
        key @0 :Text;
        value @1 :Text;
  }
}

@0x8a9fc3aa86af6ad8;

struct ReactorCommand {
    className @0 :Text;
    funcName @1 :Text;

    metadata @2 :Data;
    data @3 :Data;

    kwargs @4 :List(Entry);
    struct Entry {
        key @0 :Text;
        value @1 :Text;
  }
}

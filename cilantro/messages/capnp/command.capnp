@0xd5e3356dbe5a7e85;


struct ReactorCommand {
    className @0 :Text;
    funcName @1: Text;
    kwargs @2 :List(Entry);
    struct Entry {
        key @0 :Text;
        value @1 :Text;
  }
}

struct CpDict {
    kwargs @0 :List(Entry);
    struct Entry {
        key @0 :Text;
        value @1 :Text;
  }
}

struct Map(Key, Value) {
  entries @0 :List(Entry);
  struct Entry {
    key @0 :Key;
    value @1 :Value;
  }
}

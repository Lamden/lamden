@0xd5e3356dbe5a7e85;


struct Map(Key, Value) {
  entries @0 :List(Entry);
  struct Entry {
    key @0 :Key;
    value @1 :Value;
  }
}

struct Command {
    type @0 :UInt16;
    kwargs @1 :Map(Text, Text);
}


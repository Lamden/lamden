@0xb06e5cc550bd0e32;

struct Value {
 union {
   void @0 :Void;
   bool @1 :Bool;

   int8 @2 :Int8;
   int16 @3 :Int16;
   int32 @4 :Int32;
   int64 @5 :Int64;
   uint8 @6 :UInt8;
   uint16 @7 :UInt16;
   uint32 @8 :UInt32;
   uint64 @9 :UInt64;

   fixedPoint @10 :Text;

   float32 @11 :Float32;
   float64 @12 :Float64;

   text @13 :Text;
   data @14 :Data;

   list @15 :AnyPointer;

   enum @16 :UInt16;
   struct @17 :AnyPointer;

   anyPointer @18 :AnyPointer;
 }
}


struct Map(Key, Value) {
  entries @0 :List(Entry);
  struct Entry {
    key @0 :Key;
    value @1 :Value;
  }
}


struct Kwargs {
    kwargs @0: Map(Text, Value);
}


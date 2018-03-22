@0xb06e5cc550bd0e32

struct Value {
 # Represents a value, e.g. a field default value, constant value, or annotation value.

 union {
   # The ordinals intentionally match those of Type.

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
   float32 @10 :Float32;
   float64 @11 :Float64;
   text @12 :Text;
   data @13 :Data;

   list @14 :AnyPointer;

   enum @15 :UInt16;
   struct @16 :AnyPointer;

   interface @17 :Void;
   # The only interface value that can be represented statically is "null", whose methods always
   # throw exceptions.

   anyPointer @18 :AnyPointer;
 }
}
@0xa927b5c622e348f9

struct Transaction {

  enum TxType {
    std @0;
    vote @1;
    stamp @2;
  }

  id @3 :UInt32;
  type @4 :TxType;
  payload @2 :Data;
  proof @5 :Text;
  signature @6 :Text;
}
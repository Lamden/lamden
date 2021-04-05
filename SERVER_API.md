# Lamden Node Server API

All nodes run a web server for people to query the current state and blockchain from. Masternodes are the only ones the ingest and validate transactions. All nodes process those transactions, publish the results, and offer read-only API services to the public.

### Required API Routes

---

#### Submit Transaction
Adds a transaction to a node's pool if it is formatted and the sender can afford to send it.

```json
curl -X POST http://<node_ip>/ -d <Transaction JSON>
```
##### Arguments
Accepts a Lamden transaction sent as the body of the request.

##### Returns
```
{
  "success": "Transaction successfully submitted to the network.",
  "hash": <SHA3 256 Hexedecimal String>
}
```
##### Errors
See Transaction Response Errors.

---

#### Ping Node
Returns a simple status message if the node is online.

```json
curl -X GET http://<node_ip>/ping
```
##### Arguments
None

##### Returns
```
{
  "status": "online"
}
```

---

#### Get Node's Identity
Returns the verifying key of the node.

```json
curl -X GET http://<node_ip>/id
```
##### Arguments
None

##### Returns
```
{
  "verifying_key": <Verifying Key>
}
```

---

#### Get Current Nonce
Returns the nonce of a verifying key.

```json
curl -X GET http://<node_ip>/nonce/<Verifying Key>
```
##### Arguments
A ED25519 verifying key.

##### Returns
```
{
  "nonce": <Non-negative number>,
  "processor": <Verifying Key of the Node Responding to the Request>,
  "sender": <Provided Verifying Key>
}
```

# Lamden Node Server API

All nodes run a web server for people to query the current state and blockchain from. Masternodes are the only ones the ingest and validate transactions. All nodes process those transactions, publish the results, and offer read-only API services to the public.

### Required API Routes

---

#### Submit Transaction

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

#### Submit Transaction

```json
curl -X GET http://<node_ip>/ping
```
##### Arguments
None

##### Returns
```json
{
  "status": "online"
}
```

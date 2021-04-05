# Lamden Node Server API

All nodes run a web server for people to query the current state and blockchain from. Masternodes are the only ones the ingest and validate transactions. All nodes process those transactions, publish the results, and offer read-only API services to the public.

### Required API Routes



#### Submit Transaction

```json
POST http://<node_ip>/
```


self.app.add_route(self.submit_transaction, '/', methods=['POST', 'OPTIONS'])


Arguments: None

Output: 
```json
{
  "contracts": [
    "string",
  ]
 }
```
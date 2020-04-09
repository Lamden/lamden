## Lamden Blockchain
### Get a computer with Ubuntu 18.04.
* DigitalOcean droplets are our favorites if you are new.

* * *

### Install Pip3
```bash
sudo apt-get update
sudo apt-get install python3-pip -y
```

### Other Pip3 Pkg
```bash
pip3 install --upgrade pip setuptools
```

### Install RocksDB
```bash
sudo apt-get install libgflags-dev libsnappy-dev zlib1g-dev libbz2-dev liblz4-dev libzstd-dev libbz2-dev -y
sudo apt-get install librocksdb-dev -y
```

### Install MongoDB
```bash
sudo apt-get install -y mongodb
```

### Install Haveged (Recommended)
For some reason, DigitalOcean droplets, and perhaps other cloud providers, have `/dev/random` blocking problems. This probably is because they are running many small computers on a single Linux instance and the entropy pool dries up pretty quickly. If this doesn't make sense, install Haveged and don't worry about it.

If it does, `libsodium`, which is the public-private key cryptography library we use, uses `/dev/random` with no option to use `/dev/urandom`. Haveged solves this problem.

```bash
sudo apt-get install haveged -y
systemctl start haveged
systemctl enable haveged
```

### Install Contracting
```
git clone https://github.com/Lamden/contracting.git
cd contracting
git fetch
git checkout dev
python3 setup.py develop
```

### Install Cilantro
```
cd ~
git clone https://github.com/Lamden/cilantro-enterprise.git
cd cilantro-enterprise
git fetch
git checkout ori1-rel-gov-socks
python3 setup.py develop
```

### Setup and run Mongo
```
mongod --dbpath ~/blocks --logpath ~/logs.log --bind_ip_all --fork
# cd cilantro-enterprise/scripts
# python3 create_user.py # nolonger needed
```

### Start Rocks (Python Driver) and fork the process
```
pip3 install python-rocksdb

rocks serve &
```

### Make a Constitution
```
nano ~/constitution.json

{
  "masternodes": [<list of vks here>],
  "masternode_min_quorum": <int>,
  "delegates": [<list of vks here>],
  "delegate_min_quorum": <int>
}

Ctrl+X, save the file.
```

### Start your node
```
cil <masternode | delegate> -k <sk in hex format> -bn <list of ip addresses that are currently online>
```

## Lamden Blockchain
### Get a computer with Ubuntu 18.04.
* DigitalOcean droplets are our favorites if you are new.

* * *

### Install Pip3
```bash
sudo apt-get update
sudo apt-get python3-pip -y
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
git checkout rel_gov_debug
python3 setup.py develop
```

### Setup and run Mongo
```
mongod --dbpath ~/blocks --logpath ~/logs --bind_ip_all
cd cilantro-enterprise/scripts
python3 create_user.py
```

### Open your ports:
```
sudo ufw allow 443/tcp
sudo ufw allow 8080/tcp
sudo ufw allow 10000:10999/tcp
```
* * *

### Download Cilantro
```
git clone https://github.com/Lamden/cilantro-enterprise.git
cd cilantro-enterprise
git checkout rel_gov_debug
```
* * *
### Install Cilantro
```
sudo python3 setup.py develop
```
NOTE: Capnproto takes a *very* long time to install because it compiles from source. Please be patient!!

* * *

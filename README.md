## Lamden Blockchain
### Get a computer with Ubuntu 18.04.
* DigitalOcean droplets are our favorites if you are new.

* * *

### Install Pip3
```bash
sudo apt-get update
sudo apt-get python3-pip
```

### Install RocksDB
```bash
sudo apt-get install libgflags-dev
sudo apt-get install libsnappy-dev
sudo apt-get install zlib1g-dev
sudo apt-get install libbz2-dev
sudo apt-get install liblz4-dev
sudo apt-get install libzstd-dev
sudo apt-get install libbz2-dev

sudo apt-get install librocksdb-dev
```

### Install MongoDB
```bash
sudo apt-get install -y mongodb
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
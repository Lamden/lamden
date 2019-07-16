<p align="center">  <img src="../dev/logo500.png" width="40%">
</p>

## Running your RCNet node
### Get a computer with Ubuntu 18.04.
* DigitalOcean droplets are our favorites if you are new.

* * *

### Install prerequisites:
Install Git if your OS doesn't have it preinstalled

##### Cent OS
```
sudo yum install git
```
##### Ubuntu
```
sudo apt-get install git-core
```

### Install Node requirements
```
sudo apt update
sudo apt install -y python3-pip redis-server mongodb
```
* * *

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
git checkout demo
```
* * *
### Install Cilantro
```
sudo python3 setup.py develop
sudo make install
```
NOTE: Capnproto takes a *very* long time to install because it compiles from source. Please be patient!!

* * *
### Setup Node Configuration
```
python3 scripts/setup_node.py
```
### Enter your Signing Key (Private Key) as a Hex String
Find your Signing Key / Private Key in the Lamden Vault Chrome Plugin. If you don't have a wallet yet, get one by following the instructions here: [https://docs.lamden.io/lamden-vault/](https://docs.lamden.io/lamden-vault/)

![Image](../dev/wallet.png?raw=true)

Enter your wallet password to expose your Private Key, as shown above.

### Enter Constitution File Name
This is the file name of the initial configuration. Constitution files are located in the `constitutions` folder. If you don't know which one to use, ask an admin.

Example names: `rcnet.json`, `nojan.json`, `nohup.json`.

If you are not part of the constitution, this step will fail. You can't join the network if you are not a participant.

### Start your node
```
make stop-db
make start-db
python3 scripts/bootstrap.py
```

If you want to leave your node up and running while you log out of `ssh`, add `nohup` and `&` like this:
```
make stop-db
make start-db
nohup python3 scripts/bootstrap.py &
```

Your node is now up and running!

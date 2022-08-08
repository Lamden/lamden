## Lamden Blockchain
### Get a computer with Ubuntu 18.04.
* DigitalOcean droplets are our favorites if you are new.

* * *

### Install Pip3
```bash
sudo apt-get update
sudo apt-get install python3-pip -y
```

### Install Haveged (Recommended)
For some reason, DigitalOcean droplets, and perhaps other cloud providers, have `/dev/random` blocking problems. This probably is because they are running many small computers on a single Linux instance and the entropy pool dries up pretty quickly. If this doesn't make sense, install Haveged and don't worry about it.

If it does, `libsodium`, which is the public-private key cryptography library we use, uses `/dev/random` with no option to use `/dev/urandom`. Haveged solves this problem.

```bash
sudo apt-get install haveged -y
systemctl start haveged
systemctl enable haveged
```

### Install Lamden
```
pip3 install lamden
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
lamden <masternode | delegate> -k <sk in hex format> -bn <list of ip addresses that are currently online>
```

### Autoinstall
You can install a script to install the entire software.
```
wget https://raw.githubusercontent.com/Lamden/lamden/dev/INSTALL.sh
```
Always practice good saftey and examine the bash file before executing it.

# Cilantro - A Performant Blockchain that Isn't Confusing
[![Build Status](https://travis-ci.org/Lamden/cilantro.svg?branch=master)](https://travis-ci.org/Lamden/cilantro)
[![Coverage Status](https://coveralls.io/repos/github/Lamden/cilantro/badge.svg?branch=master)](https://coveralls.io/github/Lamden/cilantro?branch=master)
[![GitHub last commit](https://img.shields.io/github/last-commit/Lamden/cilantro.svg)](https://github.com/Lamden/cilantro/commits/master) 
[![GitHub contributors](https://img.shields.io/github/contributors/Lamden/cilantro.svg)](https://github.com/Lamden/cilantro/graphs/contributors) 
[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![GitHub license](https://img.shields.io/github/license/Lamden/cilantro.svg)](https://github.com/Lamden/cilantro/blob/master/LICENSE)

<img src="https://github.com/Lamden/cilantro/raw/master/muncho.png" align="right"
     title="Muncho" width="340" height="290">

### Features
* 2800 transactions per second / core on a 2018 Macbook 2.2 Intel Core i7
* Smart contracting language in pure, unmodified Python
* Simple and standard APIs and tooling
* Integrates with existing IDEs for development
* Properly designed masternode and delegate governance system that optimizes to performance and reduces collusion
* Strong community support
* Atomic swap integration for cross-chain communication


### Installation
```
git clone https://github.com/lamden/cilantro
cd cilantro
make install
```

PyPi installation will be available at release of AnarchyNet.

### Smart Contract Example
```
from lamden import tau
tau.send('stu', 1000)
```

All transactions are smart contracts. All smart contracts are valid Python code. Not all Python code can run as we've restricted many of the built-in modules. However, if you expose a function, other people can import your smart contract and call it easily.

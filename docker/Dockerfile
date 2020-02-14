FROM ubuntu:18.04

# Update and install pip
RUN apt-get update
RUN apt-get install sudo
RUN sudo apt-get install -y python3-pip

# Install RocksDB
RUN sudo apt-get install -y libgflags-dev libsnappy-dev zlib1g-dev libbz2-dev liblz4-dev libzstd-dev libbz2-dev
RUN sudo apt-get install -y librocksdb-dev

# Install MongoDB
RUN sudo apt-get install -y mongodb

# Install Haveged for entropy pool
RUN sudo apt-get install -y systemd
RUN sudo apt-get install -y haveged

RUN service haveged start

# Install Contracting (dev branch)
RUN sudo apt-get install -y git
RUN git clone https://github.com/Lamden/contracting.git
RUN cd contracting
RUN git checkout dev
RUN python3 setup.py develop

# Install Cilantro-enterprise (rel_gov_debug branch)
RUN cd ~
RUN git clone https://github.com/Lamden/cilantro-enterprise.git
RUN cd cilantro-enterprise
RUN git checkout rel_gov_debug
RUN python3 setup.py develop

RUN mongod --dbpath ~/blocks --logpath ~/logs.log --bind_ip_all
RUN cd scripts
RUN python3 create_user.py

RUN rocks serve &

EXPOSE 18080
COPY app/constitution ~

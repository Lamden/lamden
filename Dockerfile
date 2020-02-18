FROM ubuntu:18.04

# Update and install pip
RUN apt-get update
RUN apt-get install sudo
RUN sudo apt-get install -y python3-pip git

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
RUN pip3 install -e git+https://github.com/Lamden/contracting.git@dev#egg=contracting
RUN pip3 install -e git+https://github.com/Lamden/cilantro-enterprise.git@rel_gov_debug#egg=cilantro_ee

EXPOSE 18080

ENTRYPOINT ["cil"]

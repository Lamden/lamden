FROM ubuntu:18.04

MAINTAINER Falcon Wong version: 0.1

COPY . /app
WORKDIR /app

ENV DEBIAN_FRONTEND noninteractive

# Install Python requirements
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        sudo ssh tar gzip ca-certificates curl \
        openssl python3.6 wget \
        python3-pip python3.6-dev build-essential \
        gcc g++ git autoconf automake \
        libffi-dev libtool dpkg \
        gsl-bin zlib1g-dev libboost-all-dev \
        nano vim \
    && pip3 install --upgrade setuptools wheel \
    && pip3 install -r requirements.txt \
    && pip3 install -r dev-requirements.txt \
    && git clone https://github.com/pyca/pynacl.git \
        && cd pynacl \
        && cythonize -ki src/nacl \
        && python3 setup.py install \
        && cd - \
    && apt install -y redis-server \
    && rm -rf pynacl capnproto 2>/dev/null \
    && apt-get remove -y --allow-remove-essential \
        build-essential \
        gcc g++ \
        libffi-dev libtool \
        gsl-bin zlib1g-dev libboost-all-dev \
        autoconf automake \
    && rm -rf /var/lib/apt/lists/*

CMD bash ./scripts/start_redis.sh

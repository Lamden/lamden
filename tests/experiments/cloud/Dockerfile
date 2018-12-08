FROM lamden/cilantro

MAINTAINER Falcon Wong version: 0.1

COPY . /app
WORKDIR /app

ENV DOCKERIZE_VERSION v0.6.1
ENV DEBIAN_FRONTEND noninteractive

# Install Mongo
RUN apt-get update \
    && apt-get install -y software-properties-common \
    && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 9DA31620334BD75D9DCB49F368818C72E52529D4 \
    && add-apt-repository 'deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.0 multiverse'  \
    && apt-get update \
    && apt-get install -y mongodb \
    && apt-get remove -y software-properties-common

CMD bash ./scripts/start_redis_mongo.sh

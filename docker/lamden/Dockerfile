FROM python:3.6.9

ARG LAMDEN_BRANCH
ARG CONTRACTING_BRANCH
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y libhdf5-dev

workdir /
RUN git clone https://github.com/Lamden/contracting && cd contracting && git checkout -b ${CONTRACTING_BRANCH} origin/${CONTRACTING_BRANCH} && python setup.py install && cd ..
RUN git clone https://github.com/Lamden/lamden.git && cd lamden && git checkout -b ${LAMDEN_BRANCH} origin/${LAMDEN_BRANCH} && python setup.py install && cd ..

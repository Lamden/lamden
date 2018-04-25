#!/bin/sh

START_SCRIPT=$1

mysqld \
    --skip-grant-tables \
    --skip-innodb \
    --collation-server latin1_bin \
    --default-storage-engine ROCKSDB \
    --default-tmp-storage-engine MyISAM \
    --binlog_format ROW \
    --user=$(cat /etc/hostname) &

mkdir -p logs
python3.6 $START_SCRIPT

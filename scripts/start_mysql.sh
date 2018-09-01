#!/bin/bash
set -ex

export database=cilantro_dev
export host=127.0.0.1

echo "Waiting for mysqld on $host:3306"
dockerize -wait tcp://$host:3306 -timeout 1m

mysql -h $host -e "CREATE DATABASE $database /*\!40100 DEFAULT CHARACTER SET utf8 */;"
echo 'created db'

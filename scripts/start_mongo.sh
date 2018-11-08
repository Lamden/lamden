#!/bin/bash
set -exn

echo "Waiting for mongo on localhost"
mkdir -p ./data/db/logs
touch ./data/db/logs/log_mongo.log
echo 'Dir created'

mongod --dbpath ./data/db --logpath ./data/db/logs/mongo.log &
sleep 0.5;

echo 'started mongod'

echo 'Loading .ini'
sed '/[^\[\]]/d' mn_db_conf.ini | sed 's/\ //g' > tmp.ini
. tmp.ini
rm tmp.ini

mongo --eval "db.getSiblingDB('admin').createUser({ user: '$username', pwd: '$password', roles : [{ role: 'userAdminAnyDatabase', db: 'admin' }]})"

echo 'user created'

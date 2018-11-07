#!/bin/bash
set -ex

echo "Waiting for mongo on localhost"
mkdir -p /app/data/db/logs
touch /app/data/db/logs/log_mongo.log
echo 'Dir created'

mongod --dbpath /app/data/db --logpath /app/data/db/logs/mongo.log
echo 'started mongod'

mongo
use admin
db.createUser({user:"lamden",pwd:"pwd",roles:[{role:"root",db:"admin"}]})

echo 'user created'



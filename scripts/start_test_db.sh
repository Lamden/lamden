#!/bin/bash
eval $(./scripts/source_flat_ini.py db_conf.ini)
echo "mac side: $username $password $database"
docker run -dp 3306:3306 -e "username=$username" -e "password=$password" -e "database=$database" lamden/cilantro-db
docker ps
sleep 3;

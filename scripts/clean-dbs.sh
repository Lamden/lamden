echo "Cleaning Databases..."

DB_PATH=/usr/local/db/cilantro_ee
if [ -d "$DB_PATH/redis" ]; then
    echo "Deleting redis files...."
    rm -rf /usr/local/db/cilantro_ee/redis
fi
if [ -d "$DB_PATH/mongo" ]; then
    echo "Deleting mongo files...."
    rm -rf /usr/local/db/cilantro_ee/mongo
fi


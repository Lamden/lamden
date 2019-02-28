#!/bin/bash

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CILANTRO_BASE="$DIR/../../"

localTag=$(bash ${DIR}/generate_tag.sh)

echo -e "--------------------------------------------"
echo -e "Building docker images with tag $localTag"

echo -e "\n--------------------------------------------"
echo -e "Building base image...\n"
docker build -t lamden/cilantro_ee_base:$localTag -f $CILANTRO_BASE/docker/cilantro_ee_base $CILANTRO_BASE
echo -e "--------------------------------------------"

echo -e "\n--------------------------------------------"
echo -e "Building light image...\n"
docker build  --build-arg BASE=lamden/cilantro_ee_base:$localTag -t lamden/cilantro_ee_light:$localTag -f $CILANTRO_BASE/docker/cilantro_ee_light $CILANTRO_BASE
echo -e "--------------------------------------------"

echo -e "\n--------------------------------------------"
echo -e "Building full image...\n"
docker build  --build-arg BASE=lamden/cilantro_ee_base:$localTag -t lamden/cilantro_ee_full:$localTag -f $CILANTRO_BASE/docker/cilantro_ee_full $CILANTRO_BASE
echo -e "--------------------------------------------"

#docker tag lamden/cilantro_ee_light:$localTag lamden/cilantro_ee_light:$remoteTag
#docker tag lamden/cilantro_ee_full:$localTag lamden/cilantro_ee_full:$remoteTag

if [ "$1" = "--push" ]
then
    echo -e "\nPushing docker images..."
    docker push lamden/cilantro_ee_light:$localTag
    docker push lamden/cilantro_ee_full:$localTag
fi

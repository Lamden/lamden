#!/bin/bash

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CILANTRO_BASE="$DIR/../../"

localTag=$(bash ${DIR}/generate_tag.sh)

echo -e "--------------------------------------------"
echo -e "Building docker images with..."
echo -e "branch $branch"
echo -e "commitHash $commitHash"
echo -e "dirHash $dirHash"
echo -e "localTag $localTag"
echo -e "remoteTag $remoteTag"

echo -e "\n--------------------------------------------"
echo -e "Building base image...\n"
docker build -t lamden/cilantro_base:$localTag -f $CILANTRO_BASE/docker/cilantro_base $CILANTRO_BASE
echo -e "--------------------------------------------"

echo -e "\n--------------------------------------------"
echo -e "Building light image...\n"
docker build  --build-arg BASE=lamden/cilantro_base:$localTag -t lamden/cilantro_light:$localTag -f $CILANTRO_BASE/docker/cilantro_light $CILANTRO_BASE
echo -e "--------------------------------------------"

echo -e "\n--------------------------------------------"
echo -e "Building full image...\n"
docker build  --build-arg BASE=lamden/cilantro_base:$localTag -t lamden/cilantro_full:$localTag -f $CILANTRO_BASE/docker/cilantro_full $CILANTRO_BASE
echo -e "--------------------------------------------"

#docker tag lamden/cilantro_light:$localTag lamden/cilantro_light:$remoteTag
#docker tag lamden/cilantro_full:$localTag lamden/cilantro_full:$remoteTag

if [ "$1" = "--push" ]
then
    echo -e "\nPushing docker images..."
    docker push lamden/cilantro_light:$localTag
    docker push lamden/cilantro_full:$localTag
fi

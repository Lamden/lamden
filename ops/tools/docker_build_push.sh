#!/bin/bash

branch=$(git branch | grep \* | cut -d ' ' -f2)

commitHash=$(git rev-parse HEAD)
commitHash=${commitHash:0:8}

dirHash=$(python3  ops/tools/cilantrohasher.py)
dirHash=${dirHash:0:8}

remoteTag="$branch-$commitHash"
localTag="$branch-$commitHash-$dirHash"

echo -e "--------------------------------------------"
echo -e "Building docker images with..."
echo -e "branch $branch"
echo -e "commitHash $commitHash"
echo -e "dirHash $dirHash"
echo -e "localTag $localTag"
echo -e "remoteTag $remoteTag"

echo -e "\n--------------------------------------------"
echo -e "Building base image...\n"
docker build -t lamden/cilantro_base:$localTag -f docker/cilantro_base .
echo -e "--------------------------------------------"

echo -e "\n--------------------------------------------"
echo -e "Building light image...\n"
docker build  --build-arg BASE=lamden/cilantro_base:$localTag -t lamden/cilantro_light:$localTag -f docker/cilantro_light .
echo -e "--------------------------------------------"

echo -e "\n--------------------------------------------"
echo -e "Building full image...\n"
docker build  --build-arg BASE=lamden/cilantro_base:$localTag -t lamden/cilantro_full:$localTag -f docker/cilantro_full .
echo -e "--------------------------------------------"

#docker tag lamden/cilantro_light:$localTag lamden/cilantro_light:$remoteTag
#docker tag lamden/cilantro_full:$localTag lamden/cilantro_full:$remoteTag

if [ "$1" = "--push" ]
then
    echo -e "\nPushing docker images..."
    docker push lamden/cilantro_light:$localTag
    docker push lamden/cilantro_full:$localTag
fi


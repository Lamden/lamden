#!/bin/bash

branch=$(git branch | grep \* | cut -d ' ' -f2)

commitHash=$(git rev-parse HEAD)
commitHash=${commitHash:0:8}

dirHash=$(python3  ops/tools/cilantrohasher.py)
dirHash=${dirHash:0:8}

remoteTag="$branch-$commitHash"
localTag="$branch-$commitHash-$dirHash"

if [ "$1" == "remote" ]
then
    echo $remoteTag
elif [ "$1" == "local" ]
then
    echo $localTag
else
    echo "First arg must be 'local' or 'remote'"
fi

#!/bin/bash

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CILANTRO_BASE="$DIR/../../"

branch=$(git branch | grep \* | cut -d ' ' -f2)

commitHash=$(git rev-parse HEAD)
commitHash=${commitHash:0:8}

if [ -z "$CIRCLECI" ]
then
    dirHash=$(python3  ${CILANTRO_BASE}/ops/tools/cilantro_eehasher.py)
    dirHash=${dirHash:0:8}
    localTag="$branch-$commitHash-$dirHash"
    echo $localTag
else
    remoteTag="$branch-$commitHash"
    echo $remoteTag
fi

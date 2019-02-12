#!/bin/bash

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CILANTRO_BASE="$DIR/../../"

branch=$(git branch | grep \* | cut -d ' ' -f2)

commitHash=$(git rev-parse HEAD)
commitHash=${commitHash:0:8}

dirHash=$(python3  ${CILANTRO_BASE}/ops/tools/cilantrohasher.py)
dirHash=${dirHash:0:8}

remoteTag="$branch-$commitHash"
localTag="$branch-$commitHash-$dirHash"

echo $localTag

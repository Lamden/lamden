#!/bin/bash

echo "Cleaning older builds..."

ROOT_PATH=$(pwd)
if [ -d "$ROOT_PATH/dist" ]; then
    echo "Deleting older dist dir...."
    rm -rf $ROOT_PATH/dist
fi

if [ -d "$ROOT_PATH/build" ]; then
    echo "Deleting older build dir...."
    rm -rf $ROOT_PATH/build
fi

if [ -d "$ROOT_PATH/cilantro_ee.egg-info" ]; then
    echo "Deleting older cilantro egg dir...."
    rm -rf $ROOT_PATH/cilantro_ee.egg-info
fi
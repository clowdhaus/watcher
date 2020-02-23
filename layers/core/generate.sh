#!/usr/bin/env bash

set -ex

# Remove prior artifact
rm -f *.zip

# Build container, run, copy out zip file
docker build . -t layer:core
docker run --name lambdacontainer-core layer:core /bin/bash
docker cp lambdacontainer-core:layer/core.zip core.zip
docker rm lambdacontainer-core

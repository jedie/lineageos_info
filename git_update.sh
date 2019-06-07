#!/usr/bin/env bash

set -xe

git checkout lineageos16
git pull origin lineageos16

cd lineage_wiki
git pull origin master

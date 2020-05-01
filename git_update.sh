#!/usr/bin/env bash

set -xe

git checkout master
git pull origin master

cd lineage_wiki
git pull origin master

#!/usr/bin/env bash
killall cil
cil flush all
git pull
rm nohup.out

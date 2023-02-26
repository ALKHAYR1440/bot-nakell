#!/bin/bash
pid_file=save_pid.txt
if [ -e $pid_file ]
then
    kill -9 `cat $pid_file`
    rm -rf save_pid.txt
fi
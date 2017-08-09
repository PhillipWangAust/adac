#! /bin/bash
nohup python3 adac/start_consensus.py 2>1 > output.txt & disown

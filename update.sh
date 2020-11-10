#!/usr/bin/env bash

clear
git pull
sudo ./install-dependencies.sh
python3 jok3r.py toolbox --update-all --auto --check
#python3 jok3r.py toolbox --install-all --auto --check
python3 jok3r.py toolbox --show-all

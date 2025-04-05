#!/usr/bin/bash

while true; do
  echo "Starting bot...";
  python3 main.py;
  echo "Bot went down. Restart in 60 seconds...";
  sleep 60;
done;



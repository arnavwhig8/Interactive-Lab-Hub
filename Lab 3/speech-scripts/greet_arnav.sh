#!/bin/bash

echo "Hello Arnav and Shifen, welcome back!" | python3 -m piper \
  --model en_US-lessac-medium \
  --output_file greeting.wav

aplay greeting.wav

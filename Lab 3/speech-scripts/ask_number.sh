#!/bin/bash

echo "Asking the question..."
espeak "What is your zip code?"

sleep 1

echo "Recording your answer for 5 seconds..."
arecord -D plughw:3,0 -d 5 -f S16_LE -c 1 -r 16000 number_answer.wav

echo "Recording complete."


#!/bin/bash
# Trigger an immediate team-lead synthesis by touching a sentinel file.
# The daemon checks for this file and runs synthesis immediately.
SENTINEL="/home/hurin/.openclaw/team-lead/run-synthesis-now"
touch "$SENTINEL"
echo "Synthesis trigger set. The team-lead daemon will pick it up within 60 seconds."

#!/usr/bin/env python3
"""Prune expired signals from the signal bus (14-day expiry).

Usage: uv run --directory ~/.openclaw/monitor python ~/.openclaw/scripts/prune-signals.py
Cron:  0 3 * * 0   (weekly, Sunday 3am)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".openclaw/monitor"))
from shared_memory import prune_signals

pruned = prune_signals(max_age_days=14)
if pruned:
    print(f"Pruned {pruned} expired signals")

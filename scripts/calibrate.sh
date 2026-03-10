#!/bin/bash
# Record an adversarial calibration outcome.
# Usage: calibrate.sh <challenger> <challenged> <topic> <winner> <lesson> [category]
#
# Example: calibrate.sh beren tuor "fdserver microservices split" beren \
#   "Tuor over-weights architectural elegance vs delivery speed" architecture
#
# Part of the Collective Intelligence system (ADR-0009).

set -euo pipefail

if [ $# -lt 5 ]; then
    echo "Usage: calibrate.sh <challenger> <challenged> <topic> <winner> <lesson> [category]"
    echo ""
    echo "  challenger  - Agent who challenged (huor, tuor, beren)"
    echo "  challenged  - Agent who was challenged (huor, tuor, beren)"
    echo "  topic       - What the disagreement was about"
    echo "  winner      - Who Patrick agreed with (challenger or challenged name)"
    echo "  lesson      - What was learned"
    echo "  category    - Optional category (default: general)"
    echo ""
    echo "Example:"
    echo "  calibrate.sh beren tuor 'microservices split' beren 'Velocity data wins over elegance' architecture"
    exit 1
fi

CHALLENGER="$1"
CHALLENGED="$2"
TOPIC="$3"
WINNER="$4"
LESSON="$5"
CATEGORY="${6:-general}"

CALIBRATIONS_FILE="$HOME/.openclaw/knowledge/shared/calibrations.jsonl"
mkdir -p "$(dirname "$CALIBRATIONS_FILE")"

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
CAL_ID="cal-$(date -u +%Y%m%d%H%M%S)"

# Use python for safe JSON encoding
python3 -c "
import json, sys
entry = {
    'ts': '$TS',
    'challenge_id': '$CAL_ID',
    'challenger': sys.argv[1],
    'challenged': sys.argv[2],
    'topic': sys.argv[3],
    'patrick_decided': f'agree_with_{sys.argv[4]}',
    'lesson': sys.argv[5],
    'category': sys.argv[6],
}
print(json.dumps(entry))
" "$CHALLENGER" "$CHALLENGED" "$TOPIC" "$WINNER" "$LESSON" "$CATEGORY" >> "$CALIBRATIONS_FILE"

echo "Calibration recorded: $CHALLENGER challenged $CHALLENGED on '$TOPIC' → Patrick agreed with $WINNER"
echo "Saved to $CALIBRATIONS_FILE"

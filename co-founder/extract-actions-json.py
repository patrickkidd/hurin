#!/usr/bin/env python3
"""Extract proposed-actions JSON from CC output text.

Handles nested ``` code fences inside JSON strings (e.g. spawn_prompt
containing ```python blocks) by using brace-depth tracking with
string-awareness instead of regex/sed.

Usage: echo "$CC_OUTPUT" | python3 extract-actions-json.py
Exit code 0 + prints JSON on success, exit code 1 on failure.
"""
import sys
import json
import re

text = sys.stdin.read()

for marker in ['proposed-actions', 'json']:
    pattern = r'```' + marker + r'\s*\n'
    m = re.search(pattern, text)
    if m:
        rest = text[m.end():]
        brace_depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(rest):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    candidate = rest[:i+1]
                    try:
                        obj = json.loads(candidate)
                        if 'actions' in obj:
                            print(candidate)
                            sys.exit(0)
                    except json.JSONDecodeError:
                        pass
        break

sys.exit(1)

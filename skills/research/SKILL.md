# /research — Targeted Knowledge Base Research

Trigger: `/research <topic>`

## What this does

Runs an Opus research session that searches the web for information on `<topic>`, writes findings to the appropriate knowledge base directory, and updates the research log.

## Modes

### `/research <topic>`
1. Generate a task ID from the topic (e.g., `research-<sanitized-topic>`).
2. Run:

```
exec(command="/bin/bash /home/hurin/.openclaw/monitor/task-cli.sh spawn theapp research-<sanitized-topic> 'Research the following topic and write findings to the knowledge base at ~/.openclaw/knowledge/. Topic: <topic>. Use WebSearch and WebFetch to gather information. Write a structured markdown file with your findings. Include Last verified: <today> at the top. Update ~/.openclaw/knowledge/research-log.md to mark the topic as completed.'")
```

3. Reply ONLY: "Researching **<topic>** — check #tasks in ~5-10 minutes."

### `/research list`
1. Read `~/.openclaw/knowledge/research-log.md`
2. Show the pending research topics table

### `/research status`
1. Count files in each knowledge/ subdirectory
2. Show KB summary: `domain/ (N files), market/ (N files), ...`

## Rules
- Do NOT wait for the research to complete
- Do NOT add any commentary beyond what's specified
- Override the normal "route to CC" rule — just exec and confirm

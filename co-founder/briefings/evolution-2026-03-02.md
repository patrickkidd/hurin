# Co-Founder Briefing: evolution
**Date:** 2026-03-02 17:06 AKST
**Session:** 5b35f3a9-e3e7-459e-ba6d-2b292096ee01
**Turns:** 10 max

---

**Evolution Briefing — 2026-03-02**

---

**Executive Summary**

Three high-signal discoveries today. First, Anthropic published a [2026 Agentic Coding Trends Report](https://resources.anthropic.com/2026-agentic-coding-trends-report) that reads like a blueprint for where our swarm should go next — DAG-based task decomposition, event-sourced state persistence, and a metrics schema we should steal wholesale. Second, OpenClaw v2026.2.26 shipped External Secrets Management that directly solves our plaintext-tokens-in-config problem. Third, the HuggingFace [implementation guide](https://huggingface.co/blog/Svngoku/agentic-coding-trends-2026) derived from Anthropic's report contains specific architectural patterns that map almost 1:1 to gaps in our current system.

---

**Domain 1: Agent Architecture — What the Industry Is Doing That We're Not**

The Anthropic report identifies four multi-agent coordination patterns: Hierarchical Orchestration, Router + Specialists, Blackboard, and Debate/Consensus. Our system is essentially **Hierarchical Orchestration** (hurin routes, CC executes) but we're missing pieces that the report considers table stakes for production systems.

**Finding 1: DAG-based task decomposition replaces linear spawning**

The report recommends decomposing work as a Directed Acyclic Graph:
```
Nodes: spec → plan → impl → tests → docs → security_review → perf_review
Edges: Dependencies + checkpoints
Parallelism: impl runs while tests scaffolding begins
```

Our `spawn-task.sh` treats every task as an atomic unit — one worktree, one CC session, one PR. Yesterday's 10-task batch worked because the tasks were pre-decomposed by the co-founder lens into independent units. But for anything with dependencies (like T7-12 where backend tests depend on frontend changes), we have no way to express "task B depends on task A completing." The workaround is Patrick manually sequencing spawns, which defeats the purpose.

**Applicability to us:** Medium-term. We'd need a `task-graph.json` format and a scheduler in `check-agents.py` that spawns dependent tasks when prerequisites complete. Not trivial, but the payoff is being able to say "implement this feature" and have the system decompose it into spec → impl → test → PR without manual orchestration.

**Finding 2: Event-sourced state persistence — the Ralph Loop upgrade we need**

The report explicitly recommends against hidden state and instead suggests persisting:
- **Plan**: DAG + decisions with explicit representation
- **Tool calls**: Inputs/outputs for auditability
- **Workspace snapshots**: Diffs (not full copies)
- **Evaluation results**: Gating decisions with rationale

Our Ralph Loop currently captures failure logs via `capture_tmux_output()` — but as we documented yesterday, that function returns "Session was already dead" placeholders 50% of the time. The report's recommendation of **replay-based recovery** via event-sourced logs is exactly the fix. Instead of trying to capture tmux state post-mortem, we should be logging structured events as they happen.

Claude Code already writes to `task-logs/{task_id}.log` — that's our event source. The proposed action #6 from yesterday (fall back to task logs when tmux is dead) is the minimal version. The full version would parse CC's structured output (JSON mode) to extract tool calls, decisions, and error states for the Ralph Loop to reason over.

**Finding 3: The "Repo Navigator Service" concept**

The implementation guide describes a service that provides symbol search, dependency graphs, entrypoint identification, and impact analysis to agents before they start coding. This is essentially a warm-start for agent context.

Our agents currently cold-start every time — CC reads CLAUDE.md, then has to discover the codebase structure through Glob/Grep. A pre-built context document per task (like "here are the 5 files you'll touch, here are the interfaces they implement, here's the test file") would significantly reduce wasted turns. We already do a lightweight version of this in spawn prompts (specifying file paths), but making it systematic would help.

**Finding 4: Risk-based escalation scoring**

The report recommends scoring changes across dimensions: surface area (lines changed, files touched), security sensitivity, blast radius, and novelty. Low-risk changes auto-merge; medium-risk gets human approval; high-risk gets 2-person review + threat modeling.

Our system treats all PRs equally — Gemini reviews everything, Patrick merges everything. Yesterday's batch was 8 PRs of index additions and dead code removal that could have safely auto-merged. Meanwhile, a hypothetical PR touching authentication logic would get the same review treatment. Adding a risk score to `active-tasks.json` (even a simple low/medium/high based on files touched) would let us auto-merge the trivial stuff and focus Patrick's review time on what matters.

**Finding 5: Budget enforcement per agent job**

The report recommends:
```yaml
budgets:
  max_wall_clock_minutes: 240
  max_ci_minutes: 120
  max_model_cost_usd: 25
```

We're on Max plan ($0 marginal cost for CC) so model cost doesn't apply, but wall-clock and CI minutes do. We have no timeout on spawned tasks — a stuck CC session could churn for hours. `check-agents.py` detects dead sessions but not stuck-alive ones. Adding a `max_wall_clock_minutes` field to task registry and killing sessions that exceed it would prevent runaway resource usage.

Source: [2026 Agentic Coding Trends - Implementation Guide](https://huggingface.co/blog/Svngoku/agentic-coding-trends-2026)

---

**Domain 2: OpenClaw Ecosystem — What We're Missing**

**Finding 6: External Secrets Management (v2026.2.26) — ship it**

OpenClaw [v2026.2.26](https://github.com/openclaw/openclaw/releases/tag/v2026.2.26) added full `openclaw secrets` workflow: audit, configure, apply, reload with runtime snapshot activation. This directly addresses our #1 security gap: Discord bot tokens and WordPress credentials stored in plaintext in `config.sh` and `openclaw.json`.

The [security docs](https://docs.openclaw.ai/gateway/security) recommend: "Keep secrets out of prompts; pass them via env/config on the gateway host instead." We're running v2026.3.1 (the latest), so we already have this capability — we just haven't migrated to it.

The migration path:
1. `openclaw secrets audit` — find all plaintext secrets
2. `openclaw secrets configure` — set up the secrets store
3. Move `DISCORD_BOT_TOKEN`, `WP_APP_PASSWORD`, `GH_TOKEN` into the secrets store
4. Replace plaintext values in config files with `$ref` references
5. `openclaw secrets apply` — activate

This matters because `openclaw.json` and `config.sh` sit in a directory that's one careless `git init` away from being committed. The token in `openclaw.json` has Discord write permissions to our server.

**Finding 7: Thread-bound agents (ACP) — potential hurin upgrade**

The same release added "ACP thread-bound agents" that pin agent execution to conversation threads, improving state isolation and reproducibility. Currently, hurin's session resets after 15 minutes idle — meaning if Patrick starts a conversation, walks away for 20 minutes, and comes back, context is lost.

Thread-bound agents would let hurin maintain conversation state tied to Discord threads rather than a global session timer. This maps to our existing `sessions_resume` pattern (TOOLS.md documents session ID saving) but makes it automatic. Worth investigating whether this can replace our manual session ID tracking.

**Finding 8: QMD backend for workspace memory (v2026.2.2)**

OpenClaw added a "QMD backend" for workspace memory. This is potentially relevant to our agent memory problem — currently, each spawned CC instance starts fresh with only the spawn prompt and CLAUDE.md for context. If workspace memory could persist patterns learned by previous agents ("this test suite needs `uv run`, not direct pytest"), it would reduce repeated mistakes across spawns.

I couldn't find detailed docs on QMD yet — this needs a deeper dive next run.

**Finding 9: Agents Dashboard (v2026.2.2)**

OpenClaw added an Agents dashboard for managing agent files/tools/skills/models. We currently manage hurin's config by hand-editing `openclaw.json`. The dashboard (at `http://127.0.0.1:18789`) might provide a better interface for adjusting tool permissions, model routing, and skill configuration without JSON surgery.

**Finding 10: `openclaw agents bind/unbind` for account-scoped routes**

The latest release added `openclaw agents bindings`, `openclaw agents bind`, and `openclaw agents unbind` for account-scoped route management. We're currently hardcoding channel bindings in `openclaw.json`. The CLI commands might be more maintainable, especially if we add new channels.

Sources: [OpenClaw Releases](https://github.com/openclaw/openclaw/releases), [OpenClaw 2026.2.26 Analysis](https://blockchain.news/ainews/openclaw-2026-2-26-release-external-secrets-thread-bound-agents-websocket-codex-and-11-security-fixes-analysis-for-ai-deployments), [OpenClaw Security Docs](https://docs.openclaw.ai/gateway/security)

---

**Domain 3: AI Co-Founder / CTO Patterns — What Others Are Building**

**Finding 11: Amp Code's "persistent threads" pattern**

[Amp Code](https://www.secondtalent.com/resources/amp-ai-review/) implements "persistent threads" that act as living memory for projects — tracking coding conventions, library usage, architectural decisions, and testing patterns. Sub-agents handle specialized tasks and report back to the main thread, consolidating knowledge.

This is conceptually similar to our co-founder journal system, but with a key difference: their memory is **structured** (conventions, patterns, decisions as distinct categories) rather than **append-only prose** (our `journal.md`). Our journal works but it's a 1000-line append-only log that CC reads the last 150 lines of. Over time, important early insights get pushed out by recent noise.

An improvement: split journal.md into structured sections — `conventions.md`, `patterns.md`, `decisions.md` — and have each lens update only its relevant section. This preserves important knowledge indefinitely while keeping the context window focused.

**Finding 12: "Context engineering" as the successor to prompt engineering**

Multiple sources ([Mike Mason](https://mikemason.ca/writing/ai-coding-agents-jan-2026/), Anthropic's report, [The New Stack](https://thenewstack.io/memory-for-ai-agents-a-new-paradigm-of-context-engineering/)) converge on a terminology shift: **context engineering** is displacing **prompt engineering** as the critical discipline. The distinction: prompt engineering optimizes what you ask; context engineering optimizes what the agent sees before you ask.

This validates our CLAUDE.md + doc index architecture. But it also suggests we should be more systematic about what goes into spawn prompts. Currently, `spawn-task.sh` appends delivery instructions but doesn't include project conventions, recent decisions, or known pitfalls. Adding a "context preamble" that pulls relevant doc sections based on the target repo would be context engineering in practice.

**Finding 13: Temporal's "durable execution" at $5B valuation**

[Temporal raised $300M at $5B](https://www.geekwire.com/2026/temporal-raises-300m-hits-5b-valuation-as-seattle-infrastructure-startup-rides-ai-wave/) specifically because their durable execution model maps to AI agent orchestration. The core idea: long-running workflows should survive process crashes, network failures, and restarts by persisting workflow state at every step.

Our agent tasks are ephemeral — if a tmux session dies, we try to capture logs and maybe respawn, but the workflow state (what the agent decided, what it already tried, what it was about to do) is lost. Temporal's pattern of checkpoint-per-step is overkill for our scale, but the principle of **never losing workflow state** is something our Ralph Loop would benefit from. Currently, a respawned agent starts completely fresh — it doesn't know what the previous attempt tried and failed. Including the failure log in the respawn prompt (which we already plan to do via action #6) is the minimal version of durable execution.

**Finding 14: Proactive task discovery remains rare**

I searched specifically for implementations of AI systems that identify work autonomously (without being asked). Despite being flagged as a gap in our ADR-0001-status, this capability is still uncommon in production. The [Anthropic report](https://tessl.io/blog/8-trends-shaping-software-engineering-in-2026-according-to-anthropics-agentic-coding-report/) mentions "task horizons expand from minutes to days or weeks" but this is about longer autonomous runs, not about the AI deciding what to work on.

The closest pattern I found is in CI/CD self-healing systems where a "Repair Agent" [automatically activates on pipeline failure](https://optimumpartners.com/insight/how-to-architect-self-healing-ci/cd-for-agentic-ai/), reads logs, and commits fixes. We could implement a lightweight version: `check-agents.py` already monitors CI — if a master branch CI fails, it could automatically spawn a fix-CI task. This is proactive task discovery for a narrow, safe domain.

---

**Synthesis: What Actually Matters for Us Right Now**

Ranked by impact-to-effort ratio:

1. **Migrate secrets to `openclaw secrets`** — We have the feature, we haven't used it, and plaintext tokens are a real risk. This is the highest-value infrastructure improvement with zero architectural risk.

2. **Add wall-clock timeout to spawned tasks** — A `max_minutes` field in `active-tasks.json`, checked by `check-agents.py`, that kills sessions exceeding the limit. Prevents silent resource waste.

3. **Include failure context in respawn prompts** — When the Ralph Loop respawns a task, include the last 50 lines of the previous attempt's log in the new spawn prompt. This is "durable execution lite" and directly improves respawn success rate.

4. **Risk scoring for PRs** — Even a naive version (count files touched, flag if auth/payment/config files are in the diff) would let us fast-track trivial PRs and focus review time.

5. **Structured co-founder memory** — Split `journal.md` into topic files that persist important patterns. Low effort, prevents knowledge loss as the journal grows.

Items 1-3 are ready to implement. Items 4-5 need design decisions.

---

**Search Strategy Notes**

**Productive searches:**
- `Anthropic "agentic coding trends" report 2026` → Led to the HuggingFace implementation guide, which was the single most valuable source this run. The PDF itself wasn't parseable but the derived guide had all the technical detail.
- `openclaw secrets management external configuration agent 2026` → Found the v2026.2.26 release notes and security docs with concrete migration steps.
- `site:github.com/openclaw openclaw changelog release 2026` → Good for version inventory.

**Moderate searches:**
- `"AI co-founder" OR "AI CTO" autonomous task discovery persistent memory 2026` → Found Amp Code and Temporal, both useful but not as directly applicable.
- `multi-agent coding system architecture 2026` → Good overview but mostly frameworks/tools we're not using (LangGraph, AutoGen).

**Low-yield searches:**
- `AI agent failure recovery self-healing patterns autonomous coding 2026` → Mostly enterprise marketing content, not technical patterns.

**Next run, try:**
- `site:x.com "claude code" agent swarm` — Twitter/X for practitioner stories
- `"spawn" "worktree" agent coding` — Find others using our git-worktree-per-agent pattern
- `openclaw QMD workspace memory` — Deep dive on the memory backend
- `"check-agents" OR "agent monitor" cron coding` — Others monitoring agent swarms
- `claude code --resume session` — Patterns for CC session continuity
- `ACP thread-bound openclaw` — Deeper docs on thread-bound agents
- Check [OpenClaw docs](https://docs.openclaw.ai/gateway/configuration) directly next time — more structured than release notes

**Communities/blogs to monitor regularly:**
- [HuggingFace Blog](https://huggingface.co/blog) — Technical implementation guides derived from vendor reports
- [OpenClaw GitHub Releases](https://github.com/openclaw/openclaw/releases) — Feature additions we should adopt
- [Mike Mason's blog](https://mikemason.ca/writing/) — Practitioner perspective on agentic coding
- [Anthropic Resources](https://resources.anthropic.com) — Primary source for Claude-ecosystem patterns

---

**The Uncomfortable Question**

Patrick — our agent swarm achieved 80% merge rate on mechanical tasks, and the Anthropic report confirms that the industry pattern is exactly what we're doing: orchestrator + specialist agents on isolated branches. But the report also says the next level is DAG-based task decomposition where the system can express "task B depends on task A" and auto-schedule accordingly. Right now, you are the DAG scheduler — you manually decide task order, wait for dependencies, and spawn follow-ups. The T7-12 split (frontend PR merged, backend PR orphaned) is a direct consequence of having no dependency tracking. **Would you rather invest 2-3 hours building a task-graph scheduler into check-agents.py (which would let the swarm handle multi-step features autonomously), or is the current "Patrick sequences manually" approach actually fine for your task volume?**

---

```proposed-actions
{
  "actions": [
    {
      "id": "evolution-2026-03-02-1",
      "title": "Migrate plaintext secrets to openclaw secrets store",
      "category": "infrastructure",
      "effort": "small",
      "confidence": 0.85,
      "repo": "none",
      "plan": "1. Run openclaw secrets audit to identify all plaintext secrets. 2. Run openclaw secrets configure to set up the local secrets store. 3. Move DISCORD_BOT_TOKEN from openclaw.json and config.sh into secrets store. 4. Move WP_APP_PASSWORD and GH_TOKEN into secrets store. 5. Replace plaintext values with $ref references. 6. Run openclaw secrets apply. 7. Verify gateway reconnects to Discord. 8. Verify co-founder lenses still run (test one manually).",
      "spawn_prompt": "Migrate plaintext secrets in OpenClaw configuration to the new External Secrets Management system (available since v2026.2.26).\n\nContext: We're running OpenClaw v2026.3.1 on a Mac Mini M4. Secrets are currently stored in plaintext in:\n- `~/.openclaw/openclaw.json` — Discord bot token, Anthropic API key, MiniMax API key\n- `~/.openclaw/co-founder/config.sh` — Discord bot token (duplicated), WordPress app password, GitHub token path\n\nSteps:\n1. Run `openclaw secrets audit` to identify all plaintext secrets in the config\n2. Run `openclaw secrets configure` to initialize the secrets store\n3. For each secret identified, run `openclaw secrets set <key> <value>` to store it\n4. Update `~/.openclaw/openclaw.json` to use `$ref` references instead of plaintext values for:\n   - `auth.profiles.anthropic:default.apiKey`\n   - `auth.profiles.minimax:default.apiKey`\n   - `plugins.discord.token`\n5. Update `~/.openclaw/co-founder/config.sh` to source secrets from the store instead of hardcoding:\n   - `DISCORD_BOT_TOKEN` — should use `openclaw secrets get discord-bot-token` or equivalent\n   - `WP_APP_PASSWORD` — should use `openclaw secrets get wp-app-password`\n6. Run `openclaw secrets apply` to activate\n7. Verify the gateway is healthy: `curl -s http://127.0.0.1:18789/health`\n8. Verify Discord connectivity: check that hurin responds in #planning\n\nIMPORTANT: Read the docs first — `openclaw secrets --help` and https://docs.openclaw.ai/gateway/security — to understand the exact CLI syntax before making changes. If the secrets CLI doesn't work as expected, document what you find and stop.\n\nAcceptance criteria:\n1. No plaintext API keys or tokens in `~/.openclaw/openclaw.json`\n2. No plaintext passwords in `~/.openclaw/co-founder/config.sh`\n3. Gateway health check passes\n4. `openclaw secrets audit` shows no plaintext secrets remaining",
      "success_metric": "Zero plaintext secrets in config files, gateway healthy, Discord connected"
    },
    {
      "id": "evolution-2026-03-02-2",
      "title": "Add wall-clock timeout to spawned agent tasks",
      "category": "infrastructure",
      "effort": "small",
      "confidence": 0.90,
      "repo": "none",
      "plan": "1. Add max_minutes field (default 120) to task registry entries in spawn-task.sh. 2. In check-agents.py monitoring loop, compare task start time + max_minutes against current time. 3. If exceeded and tmux session still alive, kill it and mark as timed_out. 4. Log timeout to monitor.log.",
      "spawn_prompt": "Add wall-clock timeout enforcement to the agent monitoring system so stuck tasks don't run indefinitely.\n\n**File 1: `~/.openclaw/monitor/spawn-task.sh`**\nWhen registering a task in `active-tasks.json`, add a `maxMinutes` field with default value 120 (2 hours). Find the section where the task JSON object is constructed (look for `jq` commands that build the task entry) and add `\"maxMinutes\": 120` to the object.\n\n**File 2: `~/.openclaw/monitor/check-agents.py`**\nIn the main monitoring loop where tasks are checked:\n1. Read the task's `startedAt` timestamp and `maxMinutes` from the registry\n2. If `maxMinutes` is present and `datetime.now() - startedAt > timedelta(minutes=maxMinutes)`:\n   a. Kill the tmux session: `tmux kill-session -t claude-{task_id}`\n   b. Capture the last 100 lines of output before killing\n   c. Update the task status to `\"timed_out\"` in active-tasks.json\n   d. Log: `f\"Task {task_id} exceeded {max_minutes}min wall-clock limit — killed\"`\n3. If `maxMinutes` is not present in the task entry, skip the timeout check (backward compatible)\n\nAcceptance criteria:\n1. `python3 -c \"import json; d=json.load(open('check-agents.py'.replace('check-agents.py','') + '../workspace-hurin/theapp/.clawdbot/active-tasks.json')); print('OK')\"` — JSON still valid\n2. `python3 -c \"import check_agents; print('import OK')\"` from `~/.openclaw/monitor/` succeeds\n3. `bash -n ~/.openclaw/monitor/spawn-task.sh` returns 0\n4. The timeout check is backward-compatible (tasks without maxMinutes are skipped)\n5. Timed-out tasks get their output captured before the session is killed",
      "success_metric": "No more silently stuck agent sessions — tasks auto-kill after 2 hours with captured output"
    },
    {
      "id": "evolution-2026-03-02-3",
      "title": "Include failure context in Ralph Loop respawn prompts",
      "category": "infrastructure",
      "effort": "trivial",
      "confidence": 0.92,
      "repo": "none",
      "plan": "1. In check-agents.py, when preparing a respawn, read the failure log file. 2. Append last 50 lines of failure context to the respawn prompt with a PREVIOUS ATTEMPT FAILED section. 3. This gives the new agent knowledge of what went wrong.",
      "spawn_prompt": "Improve the Ralph Loop in `~/.openclaw/monitor/check-agents.py` so respawned tasks include context from the previous failure.\n\nCurrently, when a task fails and gets respawned, the new agent starts completely fresh — it doesn't know what the previous attempt tried or why it failed. This causes repeated failures.\n\nFind the respawn logic in check-agents.py (look for where `spawn-task.sh` is called for retries, or where `respawnCount` is incremented). Before the respawn call:\n\n1. Read the failure log from `~/.openclaw/monitor/failures/{task_id}.log`\n2. If the file exists and has content (not just a placeholder), extract the last 50 lines\n3. Prepend the following to the spawn prompt:\n```\n## PREVIOUS ATTEMPT FAILED (attempt {respawn_count} of 3)\n\nThe previous agent session failed. Here is the tail of its output:\n\n```\n{last_50_lines}\n```\n\nLearn from this failure. If it hit a specific error, try a different approach. If it got stuck, skip that path.\n```\n\n4. If the failure log is empty or contains only the placeholder text (\"Session was already dead\"), include a note: \"Previous attempt failed but no diagnostic output was captured. Proceed carefully and log your reasoning.\"\n\nAcceptance criteria:\n1. `python3 -c \"import check_agents; print('import OK')\"` from `~/.openclaw/monitor/` succeeds\n2. The respawn prompt includes failure context when available\n3. The respawn prompt includes a warning when no failure context is available\n4. No other functions are modified beyond the respawn logic",
      "success_metric": "Respawned agents learn from previous failures — reduced repeat failures, higher respawn success rate"
    }
  ]
}
```

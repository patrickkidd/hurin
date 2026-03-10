# Architecture Decision Records (ADRs)

Cross-project architectural decisions affecting both btcopilot and familydiagram.

## Index

| ADR | Status | Decision |
|-----|--------|----------|
| [ADR-0001](ADR-0001-agent-swarm.md) | Accepted | OpenClaw 2-tier agent setup (hurin smart router + Claude Code subprocesses) |
| [ADR-0002](ADR-0002-prompt-caching.md) | Accepted | Prompt caching: short TTL on MiniMax M2.5, heartbeat keep-warm, cache trace diagnostics |
| [ADR-0003](ADR-0003-hurin-lockdown-validation.md) | Accepted | Hurin tool lockdown (exec-only) after autonomous action incident; thinking-off cost validation |
| [ADR-0004](ADR-0004-co-founder-system.md) | Accepted | Co-founder strategic briefing system: 9 rotating lenses, journal memory, action pipeline |
| [ADR-0005](ADR-0005-action-system.md) | Accepted | Quality-gated action pipeline: GitHub Issues as source of truth, approval-required spawning |
| [ADR-0006](ADR-0006-team-lead-daemon.md) | Superseded | Team lead daemon: metrics engine, hourly synthesis, proactive auto-spawning toward MVP goals (daemon replaced by cron in ADR-0008) |
| [ADR-0007](ADR-0007-self-evolving-system.md) | Accepted | Self-evolving agent system: KB, telemetry, spawn policy engine, session learner, prompt archaeology |
| [ADR-0008](ADR-0008-three-agent-architecture.md) | Accepted | Three-agent architecture (Huor/Tuor/Beren) + team-lead daemon decomposition into cron jobs |
| [ADR-0009](ADR-0009-collective-intelligence.md) | Accepted | Collective intelligence: shared state, signal bus, episodic memory, adversarial protocols, cross-correlation |

## Template

New ADRs should use [template.md](template.md).

## Related ADRs

- [btcopilot/adrs/](../btcopilot/adrs/) - Backend/training-specific decisions
- [familydiagram/adrs/](../familydiagram/adrs/) - Desktop/mobile app-specific decisions

# Architecture Decision Records (ADRs)

Cross-project architectural decisions affecting both btcopilot and familydiagram.

## Index

| ADR | Status | Decision |
|-----|--------|----------|
| [ADR-0001](ADR-0001-agent-swarm.md) | Accepted | OpenClaw 2-tier agent setup (hurin smart router + Claude Code subprocesses) |
| [ADR-0002](ADR-0002-prompt-caching.md) | Accepted | Prompt caching strategy — long TTL, heartbeat keep-warm, cache trace diagnostics |

## Template

New ADRs should use [template.md](template.md).

## Related ADRs

- [btcopilot/adrs/](../btcopilot/adrs/) - Backend/training-specific decisions
- [familydiagram/adrs/](../familydiagram/adrs/) - Desktop/mobile app-specific decisions

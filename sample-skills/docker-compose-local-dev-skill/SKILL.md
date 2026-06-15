---
name: docker-compose-local-dev-skill
description: "Use when creating, reviewing, or troubleshooting Docker Compose local development stacks: services, ports, volumes, health checks, databases, caches, mail sinks, env files, and repeatable startup."
metadata:
  domain: devops
  scope: implementation, troubleshooting
  triggers: Docker Compose, local development stack, services, ports, volumes, health checks, env files, database container, cache container
  exclusions: production Kubernetes deployment, application feature logic, UI component design, database query tuning
  tags: docker-compose, local-dev, devops, containers
---

# Docker Compose Local Dev Skill

Use this skill when the task is local developer infrastructure rather than cloud deployment.

## Workflow

1. Identify required services and startup order.
2. Make ports explicit and avoid collisions.
3. Keep persistent volumes intentional.
4. Add health checks for services that other services depend on.
5. Separate local env values from committed defaults.
6. Prefer documented commands that a new contributor can run.
7. Verify startup and teardown without relying on hidden machine state.

## Review Checklist

- Service names are clear.
- Ports are documented.
- Data volumes are named.
- Health checks match actual readiness.
- Secrets are not committed.
- The stack can be rebuilt from a fresh clone.

## Common Supporting Skills

- `devops-engineer` for infrastructure tradeoffs.
- `systematic-debugging` for failing startup paths.

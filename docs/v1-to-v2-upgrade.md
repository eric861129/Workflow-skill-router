# Upgrade from V1 to V2

V1 remains available through `latest` and `latest-v1` at V1.3.1. Test V2 through `latest-v2` without replacing the stable channel.

1. Install the V2 Skill and validate `skill-only-fallback` behavior.
2. Install the Plugin and run its deterministic runtime/MCP checks.
3. Verify Explicit Skill Lock and support consent with the six demo scenarios.
4. Enable durable state only after host handshake and content preflight.
5. Treat the 80 fixtures as **Tier 0 Contract**; expect `manual-required` until a fresh execution adapter exists.

Rollback by disabling the Plugin and reinstalling the pinned V1.3.1 archive. This does not migrate V2 state backward.

Do not label the installation `hybrid-full` until step 4 passes.

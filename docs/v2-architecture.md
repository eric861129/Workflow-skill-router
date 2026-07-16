# V2 Architecture

V2 is a hybrid Skill + Plugin/MCP architecture with one Python policy core.

1. Runtime Capability Discovery merges verified host, Plugin handshake, agent snapshot, filesystem metadata, and cache without allowing cache to promote availability.
2. The Router classifies Goal relation first, then chooses exactly one of Single, Phased, or Managed Goal.
3. Explicit Skill Lock and scoped support consent are orthogonal to task size.
4. The Phase State Machine and append-only SQLite event store provide CAS, idempotency, projection rebuild, and resume refresh.
5. Native Goal state is never mutated directly; the Router returns evidence-bound status candidates.
6. Real evaluation separates **Tier 0 Contract** from fresh Behavior/Outcome. Missing adapters produce `manual-required`.

`skill-only-fallback` cannot claim durable state or sealed activation. `hybrid-full` requires verified runtime and content preflight; R2/R3 remains host-controlled.

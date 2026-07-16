# V2 架構

V2 採用 Skill + Plugin/MCP 混合架構，所有政策只存在同一份 Python core。

Runtime Discovery 合併 host、Plugin handshake、agent snapshot、filesystem 與 cache；cache 不得提升可用性。Router 先判斷 Goal relation，再選 Single、Phased 或 Managed Goal。Explicit Skill Lock 與 scoped consent 不受任務大小影響。Phase State Machine、append-only event store、CAS 與 projection rebuild 支援可靠 resume。

Native Goal 只會收到 evidence-bound status candidate，不由 Router 直接修改。**Tier 0 Contract** 不等於真實模型評測；沒有 adapter 時回 `manual-required`。`skill-only-fallback` 不得宣稱 durable state，`hybrid-full` 則必須通過 runtime 與 content preflight；R2/R3 不會降級。

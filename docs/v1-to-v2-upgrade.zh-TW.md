# 從 V1 升級到 V2

`latest` 與 `latest-v1` 仍固定 V1.3.1；請先用 `latest-v2` 測試，不要直接取代穩定版。

先驗證純 SKILL 的 `skill-only-fallback`，再安裝 Plugin、執行 deterministic runtime/MCP 檢查，最後確認 Explicit Skill Lock、support consent、resume 與 content preflight。80 個案例只是 **Tier 0 Contract**；沒有 fresh adapter 時合理狀態是 `manual-required`。

在 host handshake 與 content preflight 通過前，不得標示為 `hybrid-full`。

回復方式是停用 Plugin 並重新安裝固定的 V1.3.1 archive；V2 durable state 不會反向遷移。

---
title: 安全邊界
description: 分離 instruction consent、runtime authority、side effects 與 evaluation trust。
---

## 四個獨立決策

1. **Install：**把 Plugin 或 SKILL 放到 Codex 可以發現的位置。
2. **Activate instructions：**同意在宣告範圍內讀取或使用某個 SKILL。
3. **Authorize runtime：**透過 Host 允許 tools、files、network、subprocesses 或 secrets。
4. **Authorize side effects：**核准 deployment、messages、production changes、publication 或其他重大操作。

任何一個決策都不會自動包含下一個。

## Fail-closed 規則

- Agent observations 不能產生 Host authority。
- Runtime cache 不能把 unavailable capability 升級為可用。
- Protected route activation 需要 current snapshot、policy、consent、lease 與 bound-content receipt。
- Lease 綁定 purpose/scope、只能使用一次，並受 freshness 限制。
- Side effects 不明時阻擋驗證。
- Native Goal mutation 仍由 Host 所有。
- Evaluation executable 由 server 設定；model input 無法選擇。
- Raw model traces 與 local paths 不得進入 public artifacts。

## Risk

R0 local planning 可在 bundled control plane 執行。R1 需要更嚴格的 runtime validation；R2/R3 仍受 Codex sandbox、approval 與 permission boundaries 控制。較低的 routing risk label 不會降低 Host 自身的風險判斷。

## 相依套件決策

Plugin lockfile 會先排除已知的 High 與 Critical 相依套件風險，才接受新的 release candidate。目前 MCP SDK 的間接 HTTP adapter 仍有一項由上游追蹤的 Moderate 例外；其暴露邊界與移除條件已記錄在 [Plugin 相依套件安全決策](https://github.com/eric861129/Workflow-skill-router/blob/main/docs/governance/plugin-dependency-risk.md)。Plugin 本身只啟動 MCP stdio transport，不會啟動 HTTP listener。

## 回報弱點

依照 [SECURITY.md](https://github.com/eric861129/Workflow-skill-router/blob/main/SECURITY.md) 回報。不要在 public issue 放入 secrets、private repository data 或 exploit details。

<!-- M4-B adaptive-memory-reference:start -->
## Adaptive Workflow Memory 公開契約

公開介面共有 **20** 個 MCP tools。Memory 將 **Operational DB** 與 **Optional Memory DB** 分開；Managed write 只允許 `managed-personal`、`managed-workspace-local`，User-owned Profile 仍保留原本的寫入權限邊界。

四項決策彼此獨立：Policy autonomy、可信 Workspace binding、Profile ownership／target authority，以及 Runtime／Side-effect execution authority。可信 root 不等於 Host write grant。

沒有 **receipt evidence** 時，**Skill consistency** 必須標示為 **unavailable**；`intended-unverified` 只是規劃意圖，不是 activation proof。Memory Flight Recorder 只使用 `fixture-trace` 或 sanitized runtime record；`deterministic-local-pilot` **not Model Evidence**，也不包含真實 Personal Memory。

### 四項 Authority 決策

1. Personal Policy 決定 autonomy ceiling。
2. Workspace Policy 只能降低，不能提升。
3. Automatic materialization 僅限 managed target，遇衝突就 suppression。
4. Memory 不會推導 Host Runtime、Skill activation、Side-effect 或 User-owned Workspace-file authority。
<!-- M4-B adaptive-memory-reference:end -->

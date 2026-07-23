---
title: Explicit Skill Lock
description: 保留使用者指定 SKILL，同時避免每次自動路由都詢問。
---

<a id="problem"></a>
## 問題

使用者指定的 SKILL 必須被尊重，但每次 Router 自動加入支援能力都詢問，會讓正常工作失去可用性。靜默替換更糟：它違反使用者指令，也隱藏 context cost。

<a id="contract"></a>
## 契約

使用者未指定 SKILL 時，selection mode 是 `auto`；Router 自動選擇最小支援，不為自己的推薦詢問。使用者指定一個或多個 SKILL 時，selection mode 是 `explicit-locked`：

| 指令 | 路由合約 |
| --- | --- |
| `use` | 指名 SKILL 優先作為 Primary；新增支援必須先取得目前 Phase 的具體同意。 |
| `only` | 路由僅限指名集合；不得新增集合外支援。 |
| `all` | 每個指名 SKILL 都必須被覆蓋；集合外支援仍限於已同意的範圍。 |

公開 MCP 輸入只接受 `use`、`only` 與 `all`，不接受內部路由值。任何指令都不會啟用 SKILL，也不授予權限。啟用仍受 activation gate 約束；檔案寫入、部署、訊息、秘密與正式環境存取仍以 Host permission 為準。若指名 SKILL 不可用或不足以完成必要工作，Router 會縮小結果或回報阻礙，不得自動 fallback 或靜默替換。

Plugin 模式的 consent 不是第二次自由產生 route。`propose_support_consent` 會在詢問前持久化目前 Phase route 與 concrete support set；後續 model turn 只分類 `approved`、`rejected` 或 `unclear`，再由 `transition_support_consent` 產生 bound route。scope、revision 或 context 已漂移時一律拒絕。Skill-only 只以 advisory instructions 保留相同政策，不能宣稱 durable enforcement。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "input": {"explicit_skill_ids": ["skill:api-designer"], "semantics": "use"},
  "proposal": {"support": "skill:qa-test-planner", "scope": "verify contract"},
  "user_decision": "reject",
  "active_selections": ["skill:api-designer"]
}
```

<a id="failure-modes"></a>
## Failure modes

- 被拒絕的支援只留在 audit trail，不得出現在 activation events。
- 只改 Phase ID 不能重新詢問同一個已拒絕 proposal。
- 指定 SKILL 無法完成 mandatory work 時，Router 應限縮 outcome 或誠實阻塞，不得靜默替代。

<a id="security-boundary"></a>
## Security 與 authority boundary

SKILL consent 只允許在已宣告 scope 啟用 instruction。它不授權 Plugin 安裝、寫檔、部署、傳訊、secret 或 production access。R2/R3 仍以 Host permission 為準。

<a id="verify"></a>
## 驗證

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.routing.test_explicit_lock tests.routing.test_consent tests.integration.test_local_consent_control_plane -v
```

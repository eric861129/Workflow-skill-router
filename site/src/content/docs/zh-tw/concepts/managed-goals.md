---
title: Managed Goals
description: 協調大型工作，同時讓 native Codex Goal 維持 Host-owned。
---

<a id="problem"></a>
## 問題

大型 Goal 橫跨多個 task、repo 與 session。Flat checklist 會遺失 dependency order 與 resume context；Plugin 若直接修改 native Goal，則跨越 Host authority boundary。

<a id="contract"></a>
## 契約

Managed Goal planning 建立 dependency Work Graph。每個 Work Item 有自己的 `single` 或 `phased` envelope 與 routing decision。Resume 前必須刷新 Goal、workspace、capability 與 evidence context，scheduler 才能回傳下一個工作。

Router 可以產生 `complete` 或 `blocked` status candidate；實際 Goal state transition 由 Codex 控制。Blocked candidate 需要三個相同 blocker 的 countable turns，而且沒有 runnable required item。

已發布 beta.3 提供 4 個 always local-ready tools，另有 5 個工具維持 verified-Host path。**prepared beta.5 candidate**（**not included in published beta.3**）則提供 **4 always local-ready + 3 Router-owned conditional-local** tools。當 work graph 由 Router 擁有、已驗證，且沒有 Native Goal authority 時，`get_next_work`、回報式進度與 advisory local gate 可以完成 Router-local 閉環。這不等於 `7/12 local-ready`：Explicit Skill Lock 與 consent 維持不變，local gate 通過也不代表 Skill activation、Host evidence、deployment 或 production approval。

Native Goal scheduling 需要 `verified-host-scheduler`；formal progress path 需要 `verified-event-store` 與 `activation-receipt-verifier`；gate path 需要 `verified-evidence-store` 與 `gate-authority`。缺少 graph 時透過 `router-owned-work-graph` 要求在本機建立或 replay；graph 損毀時回傳已清理的 `internal-error`，不會捏造 Host fallback。所有不可用或不安全分支都必須 **fail closed**。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "goal_binding_id": "goal:host-42",
  "work_graph": [
    {"id": "api-contract", "depends_on": []},
    {"id": "web-delivery", "depends_on": ["api-contract"]},
    {"id": "docs-handoff", "depends_on": ["web-delivery"]}
  ],
  "host_goal_mutated": false
}
```

<a id="failure-modes"></a>
## Failure modes

- Cycle 與 overlapping ready write scopes 會被拒絕。
- Status question 不增加 semantic revision。
- Goal edit 保留 completed items，可替換 unstarted items。
- Router-owned graph 可回傳 Router-local next item；Native Goal scheduling 會回傳 `capability-unavailable`，不捏造 Host authority。

<a id="security-boundary"></a>
## Security 與 authority boundary

Goal binding 需要 Host identity。Status candidate 帶有 evidence digest，且不會自行套用。Repository access、deployment、communication 與 external side effect 仍由 Codex Host 控制。

<a id="verify"></a>
## 驗證

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.goals.test_goal_orchestrator tests.goals.test_candidates -v
```

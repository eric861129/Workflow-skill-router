---
title: Phase State Machine
description: 只有 state、evidence 與 side effect 一致時才推進工作。
---

<a id="problem"></a>
## 問題

Agent 可能在 evidence 已過期、side effect 未知，或另一個程序改變 plan 後宣稱 Phase 完成。Free-form status 無法保護長期工作免於這些 race condition。

<a id="contract"></a>
## 契約

主要路徑是 `pending -> ready -> active -> verifying -> completed`。等待與復原使用 `paused`、`awaiting-approval`、`rerouting`；terminal phases 是 `completed`、`skipped`、`failed`。每個 transition 都綁定 expected state version、plan revision 與 evidence digest。

進入 `active` 需要 entry conditions、valid route/lease 與 runtime approval。Unknown side effect 阻止 `verifying`；mandatory gate failure 阻止 `completed`。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "current": {"status": "active", "state_version": 7, "plan_revision": 2},
  "request": {"target": "verifying", "expected_state_version": 7, "expected_plan_revision": 2},
  "context": {"unknown_side_effect": false},
  "event": "PHASE_STATUS_TRANSITIONED"
}
```

<a id="failure-modes"></a>
## Failure modes

- State、plan 或 evidence drift 會以 concurrency conflict 拒絕 transition。
- Terminal phase 不可 reopen。
- Paused phase 必須經 `rerouting` 恢復，先刷新 capabilities 與 evidence。
- Advisory checks 不能抵銷 mandatory gate failure。

<a id="security-boundary"></a>
## Security 與 authority boundary

Client 提交 semantic observations，不提交 authoritative event 或 pass/fail claim。Core 衍生 state change 並驗證 activation receipt；Host 控制 approval 與 verified side-effect outcome。

<a id="verify"></a>
## 驗證

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.workflow.test_transitions tests.workflow.test_gates -v
```

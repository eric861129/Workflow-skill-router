---
title: Runtime Capability Discovery
description: 路由前先確認能力是否真的可用。
---

<a id="problem"></a>
## 問題

已安裝 SKILL 或已註冊 tool 不代表可執行。Host 可能未 exposure、尚未驗證、schema 已變更、policy 禁止使用，或 observation 已過期。

<a id="contract"></a>
## 契約

Discovery 合併 filesystem metadata、Plugin handshake、agent observations、cache hints 與 verified host evidence。每個 capability 記錄 source-qualified identity、provenance、compatibility、authentication、freshness、content identity，以及 R0–R3 的 availability。Host evidence 優先於 agent 與 cache；cache 絕不能把 unavailable 能力升格。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "input": {"capability_id": "skill:playwright", "host_exposed": true, "authenticated": true},
  "output": {
    "availability_by_risk": {"R0": "available", "R1": "available", "R2": "approval-required", "R3": "unavailable"},
    "freshness": "fresh",
    "provenance": ["plugin-handshake", "verified-host"]
  }
}
```

authoritative availability、schema、trusted content identity 或 freshness identity 改變時，snapshot ID 也會改變。

<a id="failure-modes"></a>
## Failure modes

- Provider timeout 產生明確 degraded evidence，不會靜默略過。
- 未知 authoritative field 會 fail closed。
- Filesystem metadata 不能宣稱 Host authorization。
- Stale snapshot 不能授權 R2/R3 工作。

<a id="security-boundary"></a>
## Security 與 authority boundary

Agent 可以回報觀測結果；只有 Host 能證明 exposure、authentication、approval 與 policy authority。Discovery 只有在 bound-content activation path 才讀取 SKILL instruction body；列出 metadata 不等於啟用。

<a id="verify"></a>
## 驗證

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.capabilities.test_runtime_context tests.capabilities.test_merge -v
```

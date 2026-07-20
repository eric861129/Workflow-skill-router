---
title: V2 快速開始
description: 選擇 Plugin + MCP 或純 SKILL、驗證 runtime 標籤，再檢查一條 route。
---

## 1. 選擇 runtime

Codex 支援時安裝 [Plugin + MCP](/Workflow-skill-router/zh-tw/guides/install-plugin/)；只需要指令式 fallback 時安裝[純 SKILL](/Workflow-skill-router/zh-tw/guides/install-skill/)。除非是在測試 precedence，否則不要用相同 identity 同時安裝兩者。

## 2. 驗證標籤

Plugin checkout：

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

預期結果：`runtime_profile` 是 `bundled-local-r0`；`plan_work`、`propose_support_consent`、`transition_support_consent` 與 `get_router_status` 都是 local-ready。純 SKILL 任務必須標示 `skill-only-fallback`。

## 3. 試跑三種需求

小型自動 route：

```text
替一個 API error response 補上文件。
```

預期 envelope：`single`。使用者沒有指定 SKILL，因此不應出現輔助技能 consent prompt。

Explicit Skill Lock：

```text
只使用 api-designer。未詢問前不要加入輔助技能。
```

預期：指定的 SKILL 保持 active；任何 lock 外的輔助建議都必須取得同意，被拒絕後維持 inactive。

Managed Goal：

```text
繼續跨 API、Web 與 docs 的 migration Goal。
```

預期本機行為：`plan_work` 成功、`get_next_work` 回傳 typed `capability-unavailable`，而 `get_router_status` 仍可讀取。真正排程需要 verified Host integration。

## 4. 試跑 Personal Routing Profile

Personal Routing Profiles 隨 `v2.0.0-beta.2` 提供。請在 contributor checkout 中試跑使用者自訂 Skill Tree：

```powershell
Copy-Item starter/v2/workflow-skill-router/assets/personal-routing-profile.example.json ./my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "交付 API" --work-mode phased --domain api
```

Workspace Profile 放在 `.codex/workflow-skill-router.json`。Preview 必須回報 `intended-unverified`；Runtime Capability Discovery 仍控制 activation。Skill-only 只能依相同 contract 做 `skill-only-fallback`。

## 5. 檢查證據

開啟首頁 Flight Recorder，展開每個 MCP step 查看已去識別化的 request/response JSON。`runtime-trace` 是 bundled local evidence；`fixture-trace` 透過測試 ports 證明 Host contract，不是 live Host connection。

## 下一步

- [Runtime Capability Discovery](/Workflow-skill-router/zh-tw/concepts/runtime-capability-discovery/)
- [Routing Envelopes](/Workflow-skill-router/zh-tw/concepts/routing-envelopes/)
- [Personal Routing Profiles](/Workflow-skill-router/zh-tw/concepts/personal-routing-profiles/)
- [MCP tool reference](/Workflow-skill-router/zh-tw/reference/mcp-tools/)
- [疑難排解](/Workflow-skill-router/zh-tw/guides/troubleshooting/)

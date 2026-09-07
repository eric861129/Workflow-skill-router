---
title: 設定 Workflow Memory
description: 在不提升權限的前提下，設定本機 Memory Policy、隱私、保留期限與 Managed Promotion。
---

Adaptive Workflow Memory 預設為 **default-off**。先查看狀態，不要只為了查詢就建立 Policy。

```bash
workflow-skill-router memory status
workflow-skill-router memory policy explain
```

## Data root 與固定來源

Plugin 的 durable state 位於安裝快取之外。常見 data root：Windows `%LOCALAPPDATA%\workflow-skill-router`、macOS `~/Library/Application Support/workflow-skill-router`、Linux `${XDG_DATA_HOME:-~/.local/share}/workflow-skill-router`。設定 data-root override 時以 override 為準；public-safe status 只回報來源狀態與 Digest，不回傳絕對路徑。

Personal Policy 只從 data root 下支援的固定 Memory Policy 檔名讀取。Workspace Policy 只從 MCP Client 宣告或 operator 信任的 Workspace root 之固定 `.codex` 位置讀取。相同 scope 同時出現兩種格式會視為 ambiguous 並 fail closed；Workspace symlink 也不能重新導向來源。

解析順序固定為 `disabled < observe < reviewed < automatic`。Personal 是上限，**Workspace cannot elevate Personal**。Workspace 只能關閉 capture、降低 feature autonomy、縮小 risk／target、縮短 retention，或禁止 free text。

## 可直接複製的 Policy

Canonical Starter 與 Plugin 都包含：

```text
assets/memory-policy.disabled.example.yaml
assets/memory-policy.reviewed.example.yaml
assets/memory-policy.automatic.example.yaml
```

範例副檔名為 `.yaml`，內容刻意採 JSON syntax；JSON 屬於 safe YAML 子集合。duplicate key、alias、tag、可執行值與未知欄位都會被拒絕。建議從 disabled 範例開始，只修改文件明列的欄位。

Feature override 只能收緊 preset，不能超過模式上限。`automatic` 必須保留 versioning、Backtest 與可見 promotion disclosure，且自動 target 只能是 `managed-personal`、`managed-workspace-local`；它不會取得 User-owned Profile 或 Host write authority。

## Privacy、retention 與 purge

不要保存 raw objective、secret 或 local path。一般回饋使用 typed feedback；free text 同時需要 Policy 與 operation 的明確 opt-in。Retention 先清除過期 observation，再依時間刪除超量的最舊資料。

破壞性 purge 前，先由 status／summary 取得目前 Digest。`purge_workflow_memory` 必須提供 `confirmed: true` 與相符的 expected Digest。`history-only`、`analytics-only` 只刪除 Optional Memory rows 並保留 schema。Purge 不刪除 User-owned Profile，也不會暗中刪除 Managed Profile。

## 建議導入順序

採用 `observe -> reviewed -> automatic`。每一階段都應觀察 correction、suppression 與 Backtest。`automatic` 仍是明確觸發的本機 promotion operation，維持 **no background learning**、沒有 daemon，也維持 **no telemetry**。

`skill-only` 無法宣稱 durable state 或執行 MCP transition；完整能力需使用 Plugin + MCP。缺少 receipt evidence 時維持 `intended-unverified`，Skill consistency 必須是 unavailable。


契約詞彙：`default-off`、`disabled < observe < reviewed < automatic`、
`Workspace cannot elevate Personal`、`automatic-managed`、`intended-unverified`、
`no telemetry`、`no background learning`、User-owned Profile、purge、`skill-only`，
以及建議順序 `observe -> reviewed -> automatic`。

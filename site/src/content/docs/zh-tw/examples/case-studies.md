---
title: V2 Routing 案例
description: 了解 envelope 選擇、Explicit Skill Lock 與 runtime readiness 如何改變真實 routing decision。
---

## 小型文件修正

**需求：**「替一個 API error response 補上文件。」

**決策：**使用 `single`，只選一個文件導向的 primary SKILL。使用者沒有指定 SKILL，因此不出現 consent prompt。Router 先宣告預計使用方式，再編輯、驗證連結，最後揭露實際用到的技能。

**重要性：**Router 不會把每個需求都升級成 workflow，也不會為一般自動 routing 多問一次同意。

## 多階段 API contract 變更

**需求：**「新增 endpoint、更新 OpenAPI、重新產生 client，再驗證 consumer。」

**決策：**使用 `phased`。

1. Contract 與 backend semantics。
2. Generated client propagation。
3. Consumer regression verification。

每個 phase 都重新選擇最小 SKILL 集合，通過 verification gate 後才進入下一階段。只在後面有用的技能，在對應 phase 開始前維持 inactive。

**重要性：**單一寬鬆 route 會太早載入不相關能力，也會模糊 failure ownership。

## 使用者指定一個 SKILL

**需求：**「只使用 `api-designer` review 這份 contract。」

**決策：**`single` 加 Explicit Skill Lock。`api-designer` 維持 active；若 security-sensitive 細節確實需要另一個 SKILL，Router 會把它列為 inactive support 並只詢問一次。拒絕後原始 lock 不變。

**重要性：**使用者選擇保持權威，同時仍可收到透明、可拒絕的輔助建議。

## 跨 repository migration Goal

**需求：**「繼續 API、Web 與文件 migration，直到 release gate 準備完成。」

**決策：**使用 `managed-goal`，建立 Work Items、dependencies、candidates、evidence receipts 與明確 completion criteria。在 bundled local R0 profile 中，planning 與 status 可用；verified Host ports 尚未存在時，scheduling 回傳 `capability-unavailable`。

**重要性：**Router 會如實 degradation，不會假裝本機檔案提供 native Goal mutation。

## 真實模型評測

**需求：**「用真實 model runs 證明新的 routing behavior 更好。」

**決策：**可先產生不消耗 quota 的 dry-run manifest。只有 trusted operator 提供 executable configuration 並明確授權 quota 後，才允許 Behavior/Outcome execution。Paired review 與 attestation 未通過前，結果不發布。

**重要性：**Fixture 只能證明 contract shape，不能證明 model behavior；evaluation cost 與 publication 是不同決策。

## 已發現但未授權的 capability

**需求：**「使用剛發現的 deployment connector 立即發布。」

**決策：**Discovery 可以顯示 connector 已安裝，但只要 Host exposure、authorization、policy、freshness 或 side-effect approval 任一缺失，activation 仍會被阻擋。

**重要性：**Installation 是證據，不是 authority。

---
title: 真實模型評測邊界
---

# 評測證據

**Tier 0 Contract** 只驗 deterministic compatibility。Behavior／Outcome 必須 fresh、隔離答案、sealed scoring、paired manifest，且 hard violation 為零。沒有 adapter 是 `manual-required`；沒有可信任的人工作業驗證是 `review-required`，不得顯示分數。

`skill-only-fallback` 與 `hybrid-full` 都不能自行宣告 reviewer authority。

Raw result 與 checkpoint 只能寫入已驗證的 `restricted/` 目錄。Windows DACL 必須停止繼承，且只允許目前使用者與 SYSTEM；POSIX 目錄與檔案必須分別驗證為 `0700`、`0600`。未受保護的 transcript 不得 resume。

每次 run 都必須使用不存在或空白的 output root。Preflight 會在第一次 attempt 前拒絕任何既有 report 或 artifact，避免 fresh run 失敗後，舊 sanitized report 被誤認為目前證據。

公開報告只提供安全的 case-level diagnostics：數量、match rate 與 paired delta。Prompt、expected／actual Skill、rationale 與 route payload 都保留在 restricted evidence。

Contract `workflow-skill-router.behavior-routing@2.2.0` 將目前 Phase oracle 與有狀態的 Phase-transition oracle 分開綁定，並要求 scoped consent support 必須由目前 Phase 的具體 exit evidence 證成必要。多輪 consent 與 transition case 會逐 turn 評分，正確的最後 route 不能掩蓋前面 turn 的契約失敗。歷史報表（包含 revision `2.1.0`）保留原始 case／instruction digest，不得套用新版 oracle 事後重算。執行前 runner 會重新計算 canonical path-and-SHA-256 manifest；instruction package 與宣告 digest 不一致時會 fail closed。

Paired arms 現在明確宣告不同的產品 execution mode，不再假裝兩邊都只是 instruction-only：baseline 是 `model-only`，candidate 是 `hybrid-router`。Candidate consent follow-up 中，fresh model 只回傳 `approved`、`rejected` 或 `unclear`，再由 deterministic Router 套用到 persisted proposal。Model behavior evidence 與 deterministic MCP integration evidence 必須綁定同一 source revision，才能 attestation。

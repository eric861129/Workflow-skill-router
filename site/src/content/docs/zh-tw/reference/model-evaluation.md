---
title: 真實模型評測邊界
---

# 評測證據

**Tier 0 Contract** 只驗 deterministic compatibility。Behavior／Outcome 必須 fresh、隔離答案、sealed scoring、paired manifest，且 hard violation 為零。沒有 adapter 是 `manual-required`；沒有可信任的人工作業驗證是 `review-required`，不得顯示分數。

`skill-only-fallback` 與 `hybrid-full` 都不能自行宣告 reviewer authority。

Raw result 與 checkpoint 只能寫入已驗證的 `restricted/` 目錄。Windows DACL 必須停止繼承，且只允許目前使用者與 SYSTEM；POSIX 目錄與檔案必須分別驗證為 `0700`、`0600`。未受保護的 transcript 不得 resume。

每次 run 都必須使用不存在或空白的 output root。Preflight 會在第一次 attempt 前拒絕任何既有 report 或 artifact，避免 fresh run 失敗後，舊 sanitized report 被誤認為目前證據。

公開報告只提供安全的 case-level diagnostics：數量、match rate 與 paired delta。Prompt、expected／actual Skill、rationale 與 route payload 都保留在 restricted evidence。

Contract `workflow-skill-router.behavior-routing@2.3.0` 維持完整套件 13 個案例、beta smoke 6 個案例。既有 Single、Phased 與 Managed Goal 結構案例不提供 `requested_work_mode`；`profile-explain-miss` 取代 `evaluation-manual-required`。Smoke 仍只有一個雙回合 scoped-consent 案例，因此維持 36 attempts 與 42 model turns。歷史 2.2.0 報表保留原始 case／instruction digest，不會套用新版 oracle 重算。

本合約評分公開安全的分類來源／reason codes、本機 authority、Profile explain 與多餘 consent。Goal-bound 本機 mutation、本機輸出宣稱已 activation，以及把 semantic candidate 直接持久化，都屬於 hard violation。可選的 evidence object 僅允許穩定代碼與布林值，不包含原始 prompt、instruction body、Profile 內容、路徑或評分預期。Attempt identity 會綁定 nonce、tool inventory、instruction digest、公開 case payload digest 與 model／reference-driver version。

Deterministic reference-driver 只驗證 protocol 與 scoring pipeline；it does not prove real-model behavior。Beta.4 在取得明確額度授權、完成 36 attempts／42 model turns、人工審查與 attestation 前，沒有新的真實模型證據。

Paired arms 現在明確宣告不同的產品 execution mode，不再假裝兩邊都只是 instruction-only：baseline 是 `model-only`，candidate 是 `hybrid-router`。Candidate consent follow-up 中，fresh model 只回傳 `approved`、`rejected` 或 `unclear`，再由 deterministic Router 套用到 persisted proposal。Model behavior evidence 與 deterministic MCP integration evidence 必須綁定同一 source revision，才能 attestation。

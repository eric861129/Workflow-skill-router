---
title: 真實模型評測邊界
---

# 評測證據

**Tier 0 Contract** 只驗 deterministic compatibility。Behavior／Outcome 必須 fresh、隔離答案、sealed scoring、paired manifest，且 hard violation 為零。沒有 adapter 是 `manual-required`；沒有可信任的人工作業驗證是 `review-required`，不得顯示分數。

`skill-only-fallback` 與 `hybrid-full` 都不能自行宣告 reviewer authority。

---
title: V2 路由契約
description: 每個路由工作單元都必須遵循的可檢視決策與揭露契約。
---

# V2 路由契約

Router 會針對目前的工作單元建立有邊界的決策。它不會把 Skill 選擇誤當成權限、不會暗中修改 Codex 原生 Goal，也不會宣稱 Host 尚未驗證的 Runtime 能力。

## 1. 判定請求型態

先判定 Goal relation，再選擇唯一一種 envelope：

- **Single**：單一且有邊界的意圖，只選最小必要 Primary capability。
- **Phased**：包含兩個以上不同階段；每個 Phase 都依最新證據重新路由。
- **Managed Goal**：需要恢復、里程碑或相依關係；每個 Work Item 再使用 Single 或 Phased。

結果必須記錄 envelope、runtime mode、risk、scope anchor 與目前 capability snapshot。

## 2. 鎖定使用者主導權

沒有 User-specified Skill 時，selection mode 為 `auto`：Router 選擇最小充分的 Primary 與 Supporting 組合，不需要為自己的推薦反覆詢問 consent。

存在 User-specified Skill 時，selection mode 為 `explicit-locked`。使用者指定的 Skill 具有主導權；任何額外輔助都必須先提出限定範圍的用途並取得 consent。被拒絕的輔助維持 `rejected`，同一 scope 內不得啟用或重複詢問。

## 3. 執行前宣告 Planned Skills

```text
Envelope: single | phased | managed-goal
Phase 或 Work Item: 目前工作範圍
Runtime mode: hybrid | skill-only
Planned Skills: Primary 加上已核准的 Supporting Skills
Consent: not-required | pending | granted | declined
Fallback 或 exit gate: 能力不可用時必須明示
```

`plan_work` 對應輸出 `routing_envelope`、`selection_mode`、`support_consent_required`、`planned_skill_ids` 與 `runtime_mode`。

## 4. 啟用前驗證

只有 capability identity、freshness、authority、policy revision、consent grants、risk requirements 與 activation bindings 全部通過，路由才可執行。Runtime permission、Skill consent 與 production authorization 是彼此分離的決策。

不可用能力必須回傳 typed limitation 與 fallback，不得偽裝成成功執行。

## 5. 結束後回報 Actual Skills

```text
Actual Skills: 實際開啟 instruction 或 runtime binding 的能力
Changed from plan: 增減項目與原因
Outcome: complete | limited | blocked
Evidence: route、activation、gate 或 fallback references
```

Skill 只被發現、推薦或出現在 metadata，不代表它能列入 Actual Skills。

延伸閱讀：[V2 routing guide](../guides/v2-routing.md) 與 [security boundaries](./security-boundaries.md)。

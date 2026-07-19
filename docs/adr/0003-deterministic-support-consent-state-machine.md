# ADR 0003：將輔助 SKILL 同意流程下沉至確定性 MCP 狀態機

- 狀態：Accepted
- 日期：2026-07-18

## 背景

V2 已能在 routing domain 驗證 `ConsentGrant` 與 `ConsentRejection`，但 bundled local MCP control plane 只有 `plan_work`，沒有可持久化 support proposal 與使用者決定的公開能力。現行 beta-smoke 在 fresh model process 中關閉 Plugin，第二輪要求模型自行重建完整 route。因此，它只能量測 instruction-following，不能證明混合式產品會確實保留上一輪提案、Phase scope 與使用者決定。

連續三輪真實模型評測都在 `phased-explicit-consent-approve` 產生相同 hard violation。這代表 prompt wording 已不是合適的安全邊界。

## 決策

新增兩個 bundled local R0 MCP mutation：

1. `propose_support_consent`：只接受既有 `explicit-locked` plan 的具體 Phase-level support set，將 envelope、selection mode、primary SKILL、Goal relation、Phase、revision 與 material context 一次綁定並持久化。
2. `transition_support_consent`：只接受 `approve` 或 `reject` intent，從已持久化 proposal 產生結果。呼叫端不能在 transition 時替換 primary、support set、scope 或 revision。

狀態機為 `pending -> approved | rejected`。所有轉移都具備 compare-and-swap、冪等鍵與 request digest。以下情況一律 fail closed：

- proposal 不存在或不屬於目前 session；
- current Phase 或 scope anchor 不符；
- Goal revision、plan revision 或 material context 已改變；
- proposal 已用不同決定完成；
- 同一冪等鍵對應不同語意請求。

`approve` 保留完整 proposed support set；`reject` 清空 active support set，但保留原始 proposal 作為稽核證據。此狀態機只處理「SKILL selection consent」，不取代 Plugin 安裝、sandbox、工具權限或 production authorization。

## 評測邊界

證據拆成兩層：

- `hybrid consent safety`：以 core、JSONL bridge 與 bundled MCP integration tests 證明 transition invariant 與 fail-closed 行為，零 hard violation 才可發布。
- `SKILL-only routing quality`：真實模型評測仍量測 envelope、primary/support selection 與 consent intent，但標示為 advisory；不得用它宣稱 durable consent enforcement。

後續 beta model adapter 應讓 candidate arm 明確執行 hybrid transition，而 baseline 維持 model-only。最終 route 必須由 persisted proposal 加上 model-classified intent 產生，不能由模型在第二輪自由重寫。

## 影響

- 公開 MCP surface 增加兩個 local-ready tools。
- SQLite 新增 proposal 與 transition ledger；既有 migration 不修改。
- Plugin、starter、README、架構文件與評測報告必須同步說明 hybrid 與 SKILL-only 的不同保證。
- 未安裝 Plugin/MCP 的使用者仍可載入 SKILL，但同意流程只能是 instruction-level advisory。

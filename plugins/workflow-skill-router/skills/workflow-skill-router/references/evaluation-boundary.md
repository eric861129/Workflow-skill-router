# Evaluation Boundary

- 真實模型評測必須 fresh execution、sealed case、答案隔離與可重現 manifest。
- 沒有可驗證 adapter 時回報 `manual-required`，不可用合成結果冒充模型執行。
- hard invariant 失敗時，即使平均分數較高也不得宣稱改善。
- Hybrid candidate 必須明確宣告 `hybrid-router` execution mode：模型只分類 consent intent，最終 route 由持久化 proposal 與 deterministic transition 產生。
- SKILL-only 的多輪 consent 結果只屬 advisory model evidence，不可作為 durable consent safety release gate。
- 純 SKILL fallback 的 durable state、CAS、drift 與 activation instrumentation 都是不可觀測，不得計為通過。
- 對外輸出只能使用 sanitized artifact；human attestation 與 runtime approval 不可由模型自行宣告。

# Evaluation Boundary

- 真實模型評測必須 fresh execution、sealed case、答案隔離與可重現 manifest。
- 沒有可驗證 adapter 時回報 `manual-required`，不可用合成結果冒充模型執行。
- hard invariant 失敗時，即使平均分數較高也不得宣稱改善。
- 純 SKILL fallback 的 durable state、CAS、drift 與 activation instrumentation 都是不可觀測，不得計為通過。
- 對外輸出只能使用 sanitized artifact；human attestation 與 runtime approval 不可由模型自行宣告。

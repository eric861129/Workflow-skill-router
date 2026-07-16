# Routing Protocol

1. 先判斷 Goal relation，再判斷工作規模。
2. 一次只能選擇 `single`、`phased`、`managed-goal` 其中一種 envelope。
3. `phased` 保留所有實質階段，並在每個 Phase 重新路由。
4. Explicit Skill Lock 與 envelope 正交；`preferred-primary`、`allowed-set`、`required-all` 不得混用。
5. 未指定 SKILL 時採 `auto`：自動選擇最小必要支援，不為 Router 推薦項目另外詢問同意。
6. 已指定 SKILL 時採 `explicit-locked`：新增推薦支援前必須取得 scoped consent；拒絕後不得重複詢問相同提案。
7. 執行前宣告預計使用的 SKILL，完成後列出實際使用的 SKILL 與任何差異原因。
8. R2/R3 必須保留 host approval，能力不可用時 fail closed。

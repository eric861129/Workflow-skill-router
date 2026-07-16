# Routing Protocol

1. 先判斷 Goal relation，再判斷工作規模。
2. 一次只能選擇 `single`、`phased`、`managed-goal` 其中一種 envelope。
3. `phased` 保留所有實質階段，並在每個 Phase 重新路由。
4. Explicit Skill Lock 與 envelope 正交；`preferred-primary`、`allowed-set`、`required-all` 不得混用。
5. 未經同意不得讀取或啟用推薦的支援能力；拒絕後不得重複詢問相同提案。
6. R2/R3 必須保留 host approval，能力不可用時 fail closed。

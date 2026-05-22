# 驗證清單

發布或正式依賴 workflow skill router 前，請用這份清單檢查。

## 結構

- [ ] `SKILL.md` 存在。
- [ ] `SKILL.md` 有 YAML frontmatter。
- [ ] `name` 是 hyphen-case。
- [ ] `description` 只描述何時使用，不把完整流程塞進描述。
- [ ] `references/skill-tree.md` 存在。
- [ ] `references/routing-rules.md` 存在。
- [ ] reference 檔案距離 `SKILL.md` 只有一層。

## 路由品質

- [ ] 每條路由都符合 `任務性質 -> 工作階段 -> 技術領域`。
- [ ] 每條路由選 1-4 個 SKILL。
- [ ] 每條路由有 1 個明確 primary SKILL。
- [ ] supporting SKILLs 覆蓋不同工作，不重複。
- [ ] 大型 meta SKILL 不作為預設選項。
- [ ] connector 任務優先使用 connector/plugin SKILL。

## 衝突規則

- [ ] local vs plugin 優先序已記錄。
- [ ] browser automation 的選擇規則已記錄。
- [ ] review vs GitHub connector 的選擇規則已記錄。
- [ ] file-format connector 的選擇規則已記錄。
- [ ] 使用者明確指定 SKILL 時的處理規則已記錄。

## 情境測試

至少測試這些 prompt：

```text
Design a new backend API with database schema and test plan.
```

預期：API、backend、database、QA 類 SKILL。

```text
Debug a browser-only login failure in a Vue admin app.
```

預期：frontend debugging、browser、systematic debugging，必要時包含 backend。

```text
Write a technical workflow document with Mermaid diagrams.
```

預期：documentation、writing、diagram 類 SKILL。

```text
Address unresolved GitHub PR review comments.
```

預期：GitHub connector 加上 review reasoning。

```text
Summarize recent Teams messages and draft a reply.
```

預期：Teams connector SKILL。

```text
List files in this folder.
```

預期：不需要額外路由。

## 失敗訊號

- Router 對單一任務選超過 4 個 SKILL。
- Router 對簡單單步任務也啟用多 SKILL。
- Router 對需要檔案渲染的任務選了泛用文件 SKILL，而不是 file-format connector。
- Router 忽略使用者明確指定的 SKILL。
- Router 沒有理由地同時選了等價的 local 與 plugin SKILL。

## 修正方式

- 把過大的路由拆成多個工作階段。
- 把詳細 mapping 從 `SKILL.md` 移到 `skill-tree.md`。
- 為重複出錯的情境新增 conflict rule。
- 如果 router 太常觸發，縮窄 frontmatter description。

# 驗證清單

發布或正式依賴 workflow skill router 前，請用這份清單檢查。

## 結構

- [ ] `SKILL.md` 存在。
- [ ] `SKILL.md` 有 YAML frontmatter。
- [ ] `name` 是 hyphen-case。
- [ ] `description` 只描述何時使用，不把完整流程塞進描述。
- [ ] `references/skill-tree.md` 存在。
- [ ] `references/routing-rules.md` 存在。
- [ ] reference files 與 `SKILL.md` 保持清楚的相對位置。
- [ ] starter placeholder skills 已清楚標註為 placeholder-only，或已替換成真實 template skills。

## Routing 品質

- [ ] 每條 route 都符合 `任務性質 -> 工作階段 -> 技術領域`。
- [ ] 每條 route 選擇 1-4 個 skills。
- [ ] 每條 route 有一個清楚的 Primary skill。
- [ ] Supporting skills 各自負責不同工作。
- [ ] Broad meta skills 不會成為預設選項。
- [ ] Connector tasks 優先使用 connector/plugin skills。

## Conflict Rules

- [ ] local vs plugin priority 有文件化。
- [ ] browser automation 選擇規則有文件化。
- [ ] review vs GitHub connector 選擇規則有文件化。
- [ ] file-format connector 選擇規則有文件化。
- [ ] 使用者明確指定的 skill 會被尊重。

## 情境測試

至少測試以下 prompts：

```text
Design a new backend API with database schema and test plan.
```

預期：API、backend、database、QA skills。

```text
Debug a browser-only login failure in a Vue admin app.
```

預期：frontend debugging、browser、systematic debugging，必要時包含 backend。

```text
Write a technical workflow document with Mermaid diagrams.
```

預期：documentation、writing、diagram skills。

```text
Address unresolved GitHub PR review comments.
```

預期：GitHub connector 加 review reasoning。

```text
Summarize recent Teams messages and draft a reply.
```

預期：Teams connector skills。

```text
List files in this folder.
```

預期：不需要額外 routing。

## Failure Signals

- Router 對單一任務選超過 4 個 skills。
- Router 對簡單一行指令也啟用額外 skills。
- Router 對需要 rendering fidelity 的 file-format tasks 選到 generic docs skills。
- Router 忽略使用者明確指定的 skills。
- Router 沒有理由就同時選擇等價的 local 與 plugin skills。

## 修正方向

- 把過大的 routes 拆成更小的工作階段。
- 將詳細 mappings 從 `SKILL.md` 移到 `skill-tree.md`。
- 針對重複錯誤新增 conflict rule。
- 如果 router 太常被觸發，收窄 frontmatter description。

## Public-Readiness Gate

發布 repo、release 或 template package 前，請執行：

```bash
python scripts/audit-public-readiness.py .
```

預期：

```text
OK: public-readiness audit passed
```

這會檢查 community files、downloads、site entrypoints、舊 examples、placeholder policy、明顯 private identifiers、亂碼與隱藏的 edit-link UI text。

## Lighthouse / Accessibility Gate

公開發布前，請執行正式站台品質 audit：

```bash
cd site
npm run audit:lighthouse
```

預期：

```text
OK: Lighthouse audit passed. Reports written to lighthouse-reports
```

預設門檻為 performance 70、accessibility 95、best-practices 90、SEO 90。本機 JSON 與 HTML 報告會輸出到 `site/lighthouse-reports/`，並刻意由 git ignore。

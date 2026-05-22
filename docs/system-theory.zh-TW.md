# Workflow Skill Router 系統論

Workflow Skill Router 是多 SKILL AI Agent 的一層「垂直路由」。它不增加能力本身，而是決定本次任務應該使用哪些能力、依什麼順序使用、哪些能力暫時不要使用。

## 1. 問題

當 SKILL 數量少時，平面清單很直覺：

```text
api-designer
csharp-developer
vue-expert
systematic-debugging
qa-test-planner
```

當 SKILL 增加到數十個後，平面清單會遇到：

- 選擇成本高。
- 多個 SKILL 功能重疊。
- meta skill 過度觸發。
- connector skill 被一般文件或工程 skill 取代。
- agent 一次載入過多工作流，反而降低品質。

Router 的任務是把平面能力轉成工作流決策。

## 2. 核心模型

```text
任務性質
  -> 工作階段
    -> 技術領域
      -> 1 primary SKILL + 0-3 supporting SKILLs
```

例如：

```text
架構/API/後端
  -> API 合約設計
    -> C#/.NET
      -> api-designer, csharp-developer, database-schema-designer, qa-test-planner
```

同一個技術領域在不同階段應該使用不同 SKILL：

| 工作階段 | 主要問題 | SKILL |
|---|---|---|
| 需求釐清 | 要做什麼，邊界在哪 | `requirements-clarity` |
| 合約設計 | API 資源、版本、錯誤格式 | `api-designer` |
| 實作 | C# / .NET 實作模式 | `csharp-developer` |
| 資料設計 | Schema、索引、關聯 | `database-schema-designer` |
| 驗收 | 測試案例與風險 | `qa-test-planner` |

## 3. Router 不是 Super Skill

Router 只做三件事：

1. 分類任務。
2. 選出最小必要 SKILL 組合。
3. 說明選擇理由。

Router 不應該把所有 SKILL 的完整內容塞進自己身上。否則它會變成又一個大型、低精度、容易過度觸發的 meta skill。

## 4. 建議檔案結構

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
  agents/
    openai.yaml
```

### SKILL.md

只放：

- 何時使用。
- 何時不要使用。
- 路由流程。
- 輸出合約。
- 最多選幾個 SKILL。

### skill-tree.md

放完整決策樹：

```text
任務性質 / 工作階段 / 技術領域: `skill-a`, `skill-b`, `skill-c`
```

每個葉節點最多 4 個 SKILL。

### routing-rules.md

放重疊與優先序：

- local skill vs plugin skill。
- browser vs playwright。
- review skill vs GitHub connector。
- meta skill 的使用條件。

## 5. 優先序

建議優先序：

1. 尊重使用者明確指定的 SKILL。
2. 需要外部系統時，connector/plugin SKILL 優先。
3. 一般工程判斷使用 local custom SKILL。
4. OpenAI、image、plugin、skill 安裝等任務使用 system SKILL。
5. 大型 meta SKILL 只在明確需要時使用。

## 6. SKILL 數量規則

```text
Narrow task: 1 primary SKILL
Cross-domain task: 2-4 SKILLs
More than 4: split into stages
```

如果一條路由需要 5 個以上 SKILL，代表那不是一條路由，而是一個多階段專案。

## 7. 輸出合約

```text
路由：任務性質 > 工作階段 > 技術領域
使用 SKILL：skill-a, skill-b, skill-c
原因：每個 SKILL 一句話
```

簡單任務：

```text
不需要額外路由：這是單一步驟任務，直接處理即可。
```

這個合約讓使用者可以及早修正方向，也讓 agent 不會默默啟用一堆不必要的流程。

## 8. 常見反模式

### 只保留 Router

錯誤：

```text
關掉所有其他 SKILL，只保留 workflow-skill-router。
```

正確：

```text
保留其他 SKILL，讓 router 做選擇與排序。
```

### 列出所有相關 SKILL

錯誤：

```text
UI 任務：frontend-design, ui-ux-pro-max, vue-expert, shadcn, browser, playwright, qa-test-planner, ...
```

正確：

```text
UI 任務：frontend-design, ui-ux-pro-max, vue-expert, browser
```

### 預設啟用大型 Meta Skill

大型流程應該保守使用。除非任務本身需要完整方法論，否則不要每次自動啟用。

### 忽略 Connector

要處理 GitHub、Teams、Notion、Word、Excel、Slides 等外部系統時，connector skill 應優先。

## 9. 驗證

Router 至少要通過：

- `SKILL.md` frontmatter 合法。
- 每個葉節點最多 4 個 SKILL。
- 6 個以上真實情境抽測。
- 簡單任務不觸發多 SKILL。
- connector 任務優先選 connector。

請參考 [validation-checklist.zh-TW.md](validation-checklist.zh-TW.md)。

## 10. 總結

Workflow Skill Router 的核心是：

```text
用垂直結構管理水平擴張。
```

當 SKILL 變多時，不要急著刪除，也不要讓 agent 自由散射。先建立一個薄路由層，讓每次任務只載入最少、最準、最有用的 SKILL。

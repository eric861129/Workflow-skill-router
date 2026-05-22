# Workflow Skill Router

> 多 SKILL AI Agent 的輕量路由層。

當 AI Agent 的 SKILL 越來越多，問題通常不是「缺少能力」，而是「不知道這次任務該用哪幾個能力」。Workflow Skill Router 提供一個可複製的方法論，把扁平化的 SKILL 清單整理成垂直決策樹。

Language: [English](README.en.md)

## 核心模型

```text
任務性質
  -> 工作階段
    -> 技術領域
      -> 實際應該使用的 1-4 個 SKILL
```

這個專案提供：

- 一套多 SKILL 路由方法論。
- 可直接改造的 `SKILL.md` 模板。
- `skill-tree.md` 與 `routing-rules.md` 模板。
- 一份 Codex 用的 `workflow-skill-router` 範例。
- 中英文兩套可直接貼給 AI Agent 的分類 Prompt。
- 驗證清單，協助避免過度觸發與 SKILL 爆炸。

## 為什麼需要

多 SKILL 系統常見三個問題：

1. **選擇成本變高**：同一個任務可能看起來符合很多 SKILL。
2. **觸發噪音增加**：寬泛的 meta skill 容易被不必要地啟用。
3. **執行順序模糊**：需求、設計、實作、測試、收尾被混在同一層。

Workflow Skill Router 的目標不是取代其他 SKILL，而是先做「最小必要 SKILL 組合」判斷。

```text
workflow-skill-router
  -> 選出 1 個 primary skill
  -> 選出最多 3 個 supporting skills
  -> 說明選擇原因
  -> 繼續執行真正任務
```

## 專案結構

```text
workflow-skill-router/
  README.md
  README.zh-TW.md
  README.en.md
  docs/
    system-theory.zh-TW.md
    system-theory.en.md
    validation-checklist.zh-TW.md
    validation-checklist.en.md
  prompts/
    agent-prompt.zh-TW.md
    agent-prompt.en.md
  templates/
    SKILL.md
    skill-tree.md
    routing-rules.md
  examples/
    codex-workflow-skill-router/
      SKILL.md
      references/
        skill-tree.md
        routing-rules.md
      agents/
        openai.yaml
```

## 快速開始

1. 將 `examples/codex-workflow-skill-router/` 複製到你的 Codex skills 資料夾。
2. 將 `references/skill-tree.md` 裡的範例 SKILL 名稱替換成你自己的 SKILL。
3. 用 `references/routing-rules.md` 補上你的重疊規則與優先序。
4. 確認每條葉節點路由最多只選 4 個 SKILL。
5. 用真實 prompt 測試後再正式依賴它。

Codex on Windows 的常見目標路徑：

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

## 可直接貼給 AI Agent 的 Prompt

完整繁體中文版本請看：

[prompts/agent-prompt.zh-TW.md](prompts/agent-prompt.zh-TW.md)

摘要版：

```text
請先閱讀這個專案的方法論文件，盤點我目前可用的 SKILL，然後依照「任務性質 -> 工作階段 -> 技術領域 -> 1-4 個 SKILL」建立 workflow-skill-router。

請輸出：
1. Skill Inventory Summary
2. Workflow Skill Tree
3. Routing Rules
4. Recommended workflow-skill-router files
5. 至少 6 個情境驗證

限制：不要把 router 設計成 super skill；不要建議關掉其他 SKILL；單一路由最多 4 個 SKILL。
```

## 路由輸出格式

複雜任務：

```text
路由：任務性質 > 工作階段 > 技術領域
使用 SKILL：primary-skill, supporting-skill, supporting-skill
原因：每個 SKILL 一句話
```

簡單任務：

```text
不需要額外路由：這是單一步驟任務，直接處理即可。
```

## 設計原則

- Router 不是 super skill。
- `SKILL.md` 要短。
- 完整分類樹放在 `references/skill-tree.md`。
- 衝突規則放在 `references/routing-rules.md`。
- 每條路由最多選 4 個 SKILL。
- 需要真實外部資料時，connector/plugin skill 優先。
- 大型 meta skill 預設不要自動啟用。

完整方法論請看 [docs/system-theory.zh-TW.md](docs/system-theory.zh-TW.md)。

## 範例

後端 API 任務：

```text
路由：架構/API/後端 > API 合約設計 > C#/.NET
使用 SKILL：api-designer, csharp-developer, database-schema-designer, qa-test-planner
原因：api-designer 定義 API 合約；csharp-developer 對應 .NET 實作；database-schema-designer 處理資料模型；qa-test-planner 補驗收案例。
```

前端 Debug 任務：

```text
路由：前端/Web/UI > Debug > Browser 驗證
使用 SKILL：frontend-testing-debugging, browser, systematic-debugging
原因：frontend-testing-debugging 對應渲染問題；browser 做本機視覺驗證；systematic-debugging 保持根因分析。
```

## 授權

目前尚未加入 LICENSE。若要公開讓他人使用、修改或散布，建議先加入 MIT、Apache-2.0 或其他你選擇的授權。

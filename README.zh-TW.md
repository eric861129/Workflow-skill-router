# Workflow Skill Router

> 讓多 SKILL AI Agent 先選對工作流，再開始工作。

Language: [English](README.en.md)

當 AI Agent 裝了越來越多 SKILL，真正的問題通常不是「能力不夠」，而是：

```text
這次任務到底該用哪幾個 SKILL？
哪些只是相關，但其實不該啟用？
需求、設計、實作、驗證，應該用同一組 SKILL 嗎？
```

Workflow Skill Router 是一個方法論與空白範本，協助使用者把自己的 SKILL 系統整理成垂直路由：

```text
任務性質
  -> 工作階段
    -> 技術領域
      -> 實際應該使用的 1-4 個 SKILL
```

這個專案的重點不是提供一份固定的 SKILL 清單，而是提供一套方法，讓你的 AI Agent 讀完後，可以依照你目前真的安裝的 SKILL，替你生成自己的 `workflow-skill-router`。

## 為什麼要這樣設計

### 1. 多 SKILL 不是越多越好

SKILL 增加後，Agent 會面臨「選擇問題」：

- API 任務可能同時觸發 API、後端、資料庫、測試、文件 SKILL。
- 前端任務可能同時觸發 UI、Vue、Browser、Playwright、QA SKILL。
- GitHub 任務可能需要 connector，也可能需要 code review reasoning。

如果沒有路由層，Agent 容易把「相關」誤判成「需要」。

### 2. 扁平清單無法表達工作階段

同樣是後端任務，不同階段需要不同 SKILL：

| 工作階段 | 應該思考的問題 |
|---|---|
| 需求釐清 | 要解決什麼？範圍到哪裡？ |
| API 設計 | 資源、錯誤格式、版本策略是什麼？ |
| 實作 | 用哪個框架與既有架構？ |
| 資料庫 | Schema、索引、交易邊界如何設計？ |
| 驗證 | 要測哪些成功/失敗情境？ |

Workflow Skill Router 把「技術分類」再加上一層「工作階段」，讓 Agent 不會一次把所有技能都載入。

### 3. Router 不取代 SKILL

Router 不是 super skill。它只做三件事：

1. 分類任務。
2. 選出最小必要 SKILL 組合。
3. 說明為什麼這次使用這些 SKILL。

真正的 API 設計、UI 設計、除錯、文件撰寫，仍然由原本的 SKILL 負責。

## 使用方式

### Step 1：複製空白範本

將這個資料夾複製到你的 Agent SKILL 目錄：

```text
starter/workflow-skill-router/
```

例如 Codex on Windows：

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

這是一個空白範本，包含完整規格與架構，但尚未填入你的實際 SKILL 清單。

### Step 2：把 Prompt 貼給 AI Agent

使用這份繁體中文 Prompt：

[prompts/agent-prompt.zh-TW.md](prompts/agent-prompt.zh-TW.md)

這份 Prompt 會要求 Agent：

- 先閱讀本專案方法論。
- 盤點你目前可用的 SKILL。
- 將 SKILL 依任務性質、工作階段、技術領域分類。
- 建立 `skill-tree.md` 與 `routing-rules.md`。
- 驗證每條路由最多 4 個 SKILL。

### Step 3：讓 Agent 填入你的 Router

Agent 應該更新這些範本檔案：

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
  agents/
    openai.yaml
```

填完後，這個 SKILL 就會變成你個人環境的多 SKILL 路由器。

## 空白範本內容

範本在這裡：

[starter/workflow-skill-router](starter/workflow-skill-router)

它包含：

- `SKILL.md`：路由器本體規格，保留待填欄位。
- `references/skill-tree.md`：等待 Agent 依你的 SKILL 生成分類樹。
- `references/routing-rules.md`：等待 Agent 依你的 SKILL 生成優先序與衝突規則。
- `agents/openai.yaml`：Codex 顯示 metadata 範本。

## 中文區域與英文區域

這個 repo 依語言切分內容，讓使用者可以直接選擇閱讀區域。

中文區域：

- [README.zh-TW.md](README.zh-TW.md)：繁中介紹與使用流程。
- [docs/system-theory.zh-TW.md](docs/system-theory.zh-TW.md)：方法論細節。
- [docs/validation-checklist.zh-TW.md](docs/validation-checklist.zh-TW.md)：驗證清單。
- [prompts/agent-prompt.zh-TW.md](prompts/agent-prompt.zh-TW.md)：繁中 Agent Prompt。

英文區域：

- [README.en.md](README.en.md)：英文介紹與使用流程。
- [docs/system-theory.en.md](docs/system-theory.en.md)：方法論細節。
- [docs/validation-checklist.en.md](docs/validation-checklist.en.md)：驗證清單。
- [prompts/agent-prompt.en.md](prompts/agent-prompt.en.md)：英文 Agent Prompt。

共用範本：

- [starter/workflow-skill-router](starter/workflow-skill-router)：空白 SKILL 範本。
- [templates](templates)：單檔模板。

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

- 不要關掉其他 SKILL，只保留 router。
- 不要把 router 寫成超大型 SKILL。
- 每條路由最多選 4 個 SKILL。
- Router 只負責選擇與說明，實際工作交給被選出的 SKILL。
- 需要 GitHub、Teams、Notion、Word、Excel、Browser 這類外部資料時，connector/plugin SKILL 優先。
- 如果某條路由看起來需要 5 個以上 SKILL，應該拆成多個工作階段。

## 授權

目前尚未加入 LICENSE。若要公開讓他人使用、修改或散布，建議先加入 MIT、Apache-2.0 或其他你選擇的授權。

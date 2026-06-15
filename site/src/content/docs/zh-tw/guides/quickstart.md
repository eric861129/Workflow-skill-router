---
title: 快速開始
description: 安裝 starter router、填入 skill tree，並用 validator 驗證。
---

## 1. 複製 starter

把這個資料夾複製到你的 Agent skill 目錄：

```text
starter/workflow-skill-router/
```

或直接下載可安裝的 zip：

- [空白 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)
- [查看 starter source folder](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)

如果你在 Windows 使用 Codex：

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

## 2. 請 Agent 補齊 router

使用下面的繁中 prompt，或開啟 source 檔案：

- [在 GitHub 開啟 `prompts/agent-prompt.zh-TW.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/prompts/agent-prompt.zh-TW.md)

````markdown
# Agent Prompt 繁體中文

```text
你現在要協助我根據目前環境建立一套多 SKILL 應用時的 workflow-skill-router。

請先閱讀這個專案的方法論文件：
- README.zh-TW.md
- docs/system-theory.zh-TW.md
- docs/validation-checklist.zh-TW.md
- starter/workflow-skill-router/SKILL.md
- starter/workflow-skill-router/references/skill-tree.md
- starter/workflow-skill-router/references/routing-rules.md

你的目標不是新增很多新 SKILL，也不是套用範例清單。你的目標是讀取我目前已安裝、已啟用、或目前 Agent 可讀取的 SKILL，然後把空白 starter 範本填成一個符合我環境的垂直路由系統。

請依照以下步驟進行：

1. 盤點目前可用 SKILL
   - 找出所有可被目前 Agent 使用的 SKILL。
   - 每個 SKILL 至少整理：名稱、來源、用途、適合任務、是否屬於 connector/plugin、是否屬於 meta workflow。
   - 如果環境中無法自動讀取 SKILL 清單，請先問我 SKILL 存放位置或要求我貼上清單。

2. 做功能分類
   請不要只用平面分類，請依照這個結構整理：

   任務性質
     -> 工作階段
       -> 技術領域
         -> 實際應該使用的 1-4 個 SKILL

   每個葉節點最多 4 個 SKILL。
   每個葉節點要有 1 個 primary SKILL，其他是 supporting SKILL。
   如果某個分類需要超過 4 個 SKILL，請拆成多個工作階段。

3. 建立衝突規則
   請找出功能重疊或容易誤觸發的 SKILL，並寫出選擇規則。

   例如：
   - local custom skill vs plugin connector skill
   - browser automation skill vs scripted Playwright skill
   - code review skill vs GitHub PR comment skill
   - broad meta workflow skill vs narrow task skill
   - docs/writing skill vs file-format connector skill

4. 產出 workflow-skill-router 設計並填入 starter 範本
   請輸出以下內容：

   A. Skill Inventory Summary
   - 依來源分組：custom / system / plugin / connector / unknown
   - 標記高價值 SKILL、低頻 SKILL、容易過度觸發的 SKILL

   B. Workflow Skill Tree
   - 依「任務性質 -> 工作階段 -> 技術領域 -> SKILLs」輸出
   - 每條路由最多 4 個 SKILL

   C. Routing Rules
   - 優先序
   - 衝突處理
   - 何時不要使用 router
   - 何時必須優先使用 connector/plugin

   D. Recommended workflow-skill-router Files
   - 根據 starter/workflow-skill-router/SKILL.md 產出實際 SKILL.md
   - 根據盤點結果填入 references/skill-tree.md
   - 根據衝突與優先序填入 references/routing-rules.md
   - 如果目前平台支援 UI metadata，也請填入 agents/openai.yaml 或等價設定

5. 驗證
   請用至少 6 個真實任務情境測試分類是否合理：
   - 後端 API 任務
   - 前端 UI 或瀏覽器 Debug 任務
   - 文件或架構圖任務
   - GitHub PR / CI 任務
   - 外部 connector 任務
   - 一個簡單任務，確認不會過度啟用 router

重要限制：
- 不要把 router 設計成 super skill。
- 不要建議關掉所有其他 SKILL，只保留 router。
- 不要讓單一路由選超過 4 個 SKILL。
- 不要因為某個 SKILL 相關就加入；只選本任務真正需要的。
- 不要把本 repo 的範例 SKILL 清單當成我的實際 SKILL 清單；必須以我目前環境為準。
- 若需要修改檔案，請先說明會新增或修改哪些檔案，再執行。

最後請用繁體中文回覆，並用清楚的表格與 Markdown 標題整理結果。
```

## 維護 Prompt：指定新增 SKILL 寫入既有 Router

```text
我目前已經做過一次 workflow-skill-router 設定，現在新增了以下 SKILL，請協助我把它們整合進既有的 workflow-skill-router。

新增 SKILL：
- <請貼上 SKILL 名稱、路徑或描述>
- <請貼上 SKILL 名稱、路徑或描述>

請先閱讀我目前已安裝的 workflow-skill-router：
- SKILL.md
- references/skill-tree.md
- references/routing-rules.md
- agents/openai.yaml 或等價 metadata 檔案，如果存在

你的目標不是重建整套 router，也不是把新增 SKILL 塞進所有相關分類。
你的目標是判斷這些新增 SKILL 應該在既有路由系統中扮演什麼角色，並做最小必要更新。

請依照以下步驟進行：

1. 讀取指定新增 SKILL
   - 確認每個 SKILL 的名稱、來源、用途、適合任務。
   - 判斷它是否屬於 connector/plugin、system skill、custom skill，或 meta workflow。
   - 如果無法讀取 SKILL 內容，請明確告訴我缺少哪些資訊。

2. 比對既有 workflow-skill-router
   - 檢查 references/skill-tree.md 是否已有相同或高度重疊的 SKILL。
   - 檢查 references/routing-rules.md 是否已有相關衝突規則。
   - 判斷新增 SKILL 應該新增路由、取代既有 supporting skill，或只加入衝突規則。

3. 更新路由樹
   - 每條路由仍然最多 4 個 SKILL。
   - 每條路由仍然必須有 1 個 Primary SKILL，其他是 Supporting SKILL。
   - 不要因為新增 SKILL 相關就加入；只有在它比既有 SKILL 更適合某個任務階段時才加入。
   - 如果加入後某條路由超過 4 個 SKILL，請拆成更精準的工作階段。

4. 更新衝突規則
   - 如果新增 SKILL 與既有 SKILL 功能重疊，請新增選擇規則。
   - 如果新增 SKILL 是 connector/plugin，請明確寫出何時優先使用它。
   - 如果新增 SKILL 是 meta workflow，請明確寫出何時不要預設啟用它。

5. 驗證
   - 列出修改了哪些檔案。
   - 列出新增 SKILL 被放入哪些路由。
   - 用 2-3 個任務情境測試新增路由是否合理。
   - 確認沒有任何單一路由超過 4 個 SKILL。

重要限制：
- 不要重建整個 workflow-skill-router。
- 不要移除既有 SKILL，除非它確實被新 SKILL 取代，且你有說明原因。
- 不要把新增 SKILL 加到所有看起來相關的地方。
- 若需要修改檔案，請先說明會修改哪些檔案，再執行。

最後請用繁體中文回覆，並用表格整理：新增 SKILL、建議分類、Primary/Supporting 角色、修改位置、原因。
```

## 維護 Prompt：自動盤點新增但尚未寫入 Router 的 SKILL

```text
我目前已經做過一次 workflow-skill-router 設定，但後來可能又新增了一些 SKILL。
請你協助我重新盤點目前環境，找出「已安裝或目前 Agent 可讀取，但尚未被 workflow-skill-router 記錄」的 SKILL，並判斷是否需要補進 router。

請先閱讀我目前已安裝的 workflow-skill-router：
- SKILL.md
- references/skill-tree.md
- references/routing-rules.md
- agents/openai.yaml 或等價 metadata 檔案，如果存在

接著盤點目前可用 SKILL：
- 找出所有目前 Agent 可使用、已安裝、已啟用或可讀取的 SKILL。
- 依來源整理：custom / system / plugin / connector / meta workflow / unknown。
- 與 references/skill-tree.md 和 references/routing-rules.md 比對，找出尚未記錄或只被部分記錄的 SKILL。

請依照以下步驟進行：

1. 產生差異清單
   - 已在 router 中完整記錄的 SKILL。
   - 尚未記錄，但應該補入 router 的 SKILL。
   - 尚未記錄，但不建議補入 router 的 SKILL。
   - 只需要補 routing-rules，不需要加入 skill-tree 的 SKILL。

2. 判斷是否應該補入
   請依以下標準判斷：
   - 是否能覆蓋目前 router 沒有處理的任務類型？
   - 是否比既有 SKILL 更適合作為某個路由的 Primary？
   - 是否只適合作為 Supporting？
   - 是否是 connector/plugin，必須在外部資料或特定 runtime 任務中優先使用？
   - 是否是 broad meta workflow，應避免預設啟用？

3. 更新 workflow-skill-router
   - 必要時更新 references/skill-tree.md。
   - 必要時更新 references/routing-rules.md。
   - 必要時更新 Skill Inventory Summary。
   - 每條路由最多 4 個 SKILL。
   - 每條路由必須明確標示 Primary 與 Supporting。

4. 驗證
   - 用至少 3 個情境測試新增或調整後的路由。
   - 確認簡單任務不會因此過度啟用 router。
   - 確認 connector/plugin 任務仍優先使用對應 connector/plugin SKILL。
   - 確認 meta workflow 沒有被過度加入一般路由。

重要限制：
- 不要把所有缺漏 SKILL 都補進 skill-tree。
- 不要因為 SKILL 存在就假設它一定要出現在 router。
- 不要重建整套 router；請以差異更新為主。
- 不要讓單一路由超過 4 個 SKILL。
- 若需要修改檔案，請先說明會修改哪些檔案，再執行。

最後請用繁體中文回覆，並輸出：

1. Missing Skill Diff Summary
2. Recommended Additions
3. Skills Not Added And Why
4. Updated Routes
5. Validation Results
```
````

Agent 應該先盤點可用 skills，再補齊：

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
```

## 3. 執行驗證

執行：

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

預期輸出：

```text
OK: workflow-skill-router passed validation
```

如果你想看更完整的參考，可以下載 [範本 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)。裡面包含 common engineering router 和 sample `SKILL.md` folders。

Source:

- [Common engineering router](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/common-engineering-routing)
- [Sample skills](https://github.com/eric861129/Workflow-skill-router/tree/main/sample-skills)

## 4. 試跑一條 route

丟一個複雜任務給 Agent：

```text
Debug a browser-only bug in the customer portal and add a regression check.
```

預期格式：

```text
Route: Frontend / Debugging > Browser reproduction > Customer portal
Use SKILL: frontend-debugging, browser, playwright
Reason: frontend-debugging maps UI symptoms to source; browser reproduces rendered behavior; playwright captures the regression.
```

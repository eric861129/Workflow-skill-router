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

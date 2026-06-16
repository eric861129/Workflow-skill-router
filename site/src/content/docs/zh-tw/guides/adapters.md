---
title: Claude、Cursor、Gemini Adapter Notes
description: 將 router pattern 改造成可被其他支援 custom instructions、rules 或 project context 的 Agent 使用。
---

Workflow Skill Router 是 Codex-ready，但核心 contract 是純文字。任何能讀取 project instructions、rules 或 custom context 的 Agent，都可以套用同一個 pattern：

1. 盤點可用 skills 或 workflows。
2. 建立小而清楚的 routing tree。
3. 加入 conflict rules。
4. 要求 Agent 在複雜工作前先輸出 `Route`、`Use SKILL`、`Reason`。
5. 如果 folder shape 仍符合 starter，就用 repository validator 驗證。

AI 工具的設定畫面會持續變動。這頁寫的是 adapter pattern；如果要寫精確 UI 路徑，請再查該工具最新官方文件。

## 哪些部分可移植

| 部分 | 可移植？ | 說明 |
| --- | --- | --- |
| Skill inventory | 是 | 請用該工具實際可用的 capabilities、commands、rules 作為來源。 |
| Skill tree | 是 | Plain Markdown 可以跨 Agent 使用。 |
| Routing rules | 是 | Conflict rules 是最重要的可移植部分。 |
| `SKILL.md` auto-loading | Codex-specific | 其他工具通常需要貼到 project instructions 或 rules。 |
| `agents/openai.yaml` | Codex/OpenAI-specific | 視為 metadata，不是 adapter 必要輸入。 |
| Python validator | 是 | 可驗證 starter folder shape 與 public-safe files。 |

## Claude adapter pattern

適合 Claude 能讀取 repository instructions 或 project-level context 的情境。

```text
Use Workflow Skill Router as a pre-execution routing step.

Before complex work, read the router inventory, skill tree, and routing rules. Then output:

Route: <task nature / work stage > technical domain>
Use SKILL: <one primary skill, up to three supporting skills>
Reason: <why this small working set is enough>

Do not route simple one-step questions. Do not choose more than four skills. If more skills seem necessary, split the work into stages and route the first stage.
```

建議放置方式：

- 把短版 route contract 放在 Claude 會讀取的 project 或 repository instruction surface。
- 如果工具支援 project files，把完整 skill tree 放在可連結的 Markdown file。
- 不要把 private skill folders 貼到公開 chat 或 shared artifact。

## Cursor adapter pattern

適合 Cursor 能讀取 repository rules 或 workspace instructions 的情境。

```text
For multi-step coding tasks, first run a Workflow Skill Router decision.

Choose:
- 1 primary workflow or rule set
- 0-3 supporting workflows or rule sets

Return the route before editing files. Keep the route small and explain why unrelated rules were not selected.
```

建議放置方式：

- 把短版 route contract 放在 workspace rules surface。
- 如果團隊想共享一致行為，把詳細 route examples 放進 committed docs file。
- 除非刻意使用 generic example，否則不要在公開範例放 tool-specific private paths。

## Gemini adapter pattern

適合 Gemini 能讀取 project context、custom instructions 或 uploaded Markdown 的情境。

```text
Before solving a complex request, classify it with the Workflow Skill Router pattern.

Output:
Route:
Use SKILL:
Reason:

Use the smallest working set. Prefer the primary skill that owns the work stage. Add supporting skills only for distinct actions such as reproduction, verification, documentation, or live-state inspection.
```

建議放置方式：

- 把 router 作為 project context document 或 reusable instruction。
- 範例保持短，避免長 catalog 淹沒真正任務。
- 當任務從 planning 變成 implementation、debugging 或 release closeout 時，重新 route。

## 驗證流程

如果改造後的 router 仍使用 starter folder shape，請執行：

```bash
python scripts/validate-router.py path/to/workflow-skill-router
```

如果目標工具不使用 `SKILL.md` folder shape，請手動檢查：

- 每條 route 都有一個 primary skill。
- 每條 route 最多三個 supporting skills。
- Supporting skills 各自有明確工作。
- 簡單任務可以跳過 routing。
- Conflict rules 有說明為什麼 broad skills 不會過度觸發。

## 公開分享 adapter notes

公開分享時請使用 fictional examples。不要包含私人 repository paths、內部專案名、客戶名、hostnames、tokens 或工具特定 secrets。

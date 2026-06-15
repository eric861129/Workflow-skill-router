---
title: 下載
description: 下載空白 router skill 或實戰範本 skill package。
---

## 下載套件

如果你想先安裝 router，再依照自己的 Agent skill catalog 從零開始填 skill tree，請下載空白版。

- [下載空白 SKILL](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)

如果你想直接參考一組比較完整的實戰範本，請下載範本包。

- [下載範本 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)

## 內容包含什麼

空白版包含：

```text
workflow-skill-router/
  SKILL.md
  agents/openai.yaml
  references/skill-tree.md
  references/routing-rules.md
```

範本包包含：

```text
workflow-skill-router-template/
  starter/workflow-skill-router/
  examples/common-engineering-routing/
  sample-skills/
```

範本包是公開安全版：保留實際 SKILL 寫法、常見工程情境與 routing pattern，但不包含組織名稱、私有路徑、部署細節或內部系統名稱。

## 本機重新打包

```bash
python scripts/package-downloads.py
```

## Source

- [在 GitHub 開啟 `downloads/`](https://github.com/eric861129/Workflow-skill-router/tree/main/downloads)
- [查看 package builder script](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/package-downloads.py)
- [查看 starter source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [查看 template example source](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/common-engineering-routing)
- [查看 sample skills source](https://github.com/eric861129/Workflow-skill-router/tree/main/sample-skills)

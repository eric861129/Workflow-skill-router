---
title: 下載
description: 下載空白 router skill 或實戰範本 skill package。
---

## 下載套件

如果你想先安裝 router，再依照自己的 Agent skill catalog 從零開始填 skill tree，請下載空白版。

- [下載空白 SKILL](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)

如果你想直接參考一組從真實本機 Codex skills catalog 產生的公開安全實戰範本，請下載範本包。

- [下載範本 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)
- [查看範本 manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)

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
  README.md
  MANIFEST.md
  skills/
    workflow-skill-router/
    .system/
    <public-safe skill folders>
```

範本包是公開安全版：從真實 `.codex/skills` 產生，排除 private organization-specific skills，並移除其他公開 skill 內的 private lines。

## 本機重新打包

```bash
python scripts/package-downloads.py --skills-root <path-to-local-codex-skills> --exclude-prefix <private-prefix> --exclude-name <private-skill-name> --private-marker <private-text-marker>
```

打包工具不會使用隱含的本機 skills 目錄。除非你明確加上 `--allow-no-private-filters` 並已自行檢查來源目錄，否則至少要提供一個 private filter。

## Source

- [在 GitHub 開啟 `downloads/`](https://github.com/eric861129/Workflow-skill-router/tree/main/downloads)
- [查看 package builder script](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/package-downloads.py)
- [查看範本 manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)
- [查看 starter source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)

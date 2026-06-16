---
title: Troubleshooting
description: 修正常見安裝路徑、PowerShell、Python、zip 解壓與 validator 問題。
---

如果 quickstart 沒有得到以下結果，請從這頁開始排查：

```text
OK: workflow-skill-router passed validation
```

## 安裝路徑

Codex skills 通常放在：

| 平台 | 預期 folder |
| --- | --- |
| Windows | `%USERPROFILE%\.codex\skills\workflow-skill-router` |
| macOS / Linux | `$HOME/.codex/skills/workflow-skill-router` |

Windows PowerShell 檢查：

```powershell
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Test-Path $Router
Get-ChildItem $Router
```

macOS 或 Linux 檢查：

```bash
test -d "$HOME/.codex/skills/workflow-skill-router"
ls "$HOME/.codex/skills/workflow-skill-router"
```

這個 folder 應該包含 `SKILL.md`、`agents/` 與 `references/`。

## PowerShell 問題

### `python` is not recognized

請先安裝 Python 3，然後重新打開 terminal：

```powershell
python --version
```

如果 Windows 打開 Microsoft Store，請從 python.org 安裝 Python，或到 Windows settings 關閉 Python app execution alias。

### `Invoke-WebRequest` 失敗

有些公司網路會擋 GitHub raw download。可以先從 [GitHub releases page](https://github.com/eric861129/Workflow-skill-router/releases) 用瀏覽器下載 zip，再執行：

```powershell
$Skills = Join-Path $env:USERPROFILE ".codex\skills"
New-Item -ItemType Directory -Force -Path $Skills | Out-Null
Expand-Archive -Force -Path "$env:USERPROFILE\Downloads\workflow-skill-router-blank.zip" -DestinationPath $Skills
```

### Terminal 裡中文看起來是亂碼

這常常是 console 顯示問題，不一定代表檔案壞掉。用明確 UTF-8 讀檔：

```powershell
Get-Content -Encoding UTF8 "$env:USERPROFILE\.codex\skills\workflow-skill-router\SKILL.md"
```

如果檔案本身出現 `U+FFFD` 這類 replacement-character marker，請重新下載套件。

## Zip 解壓問題

解壓後應該是這個結構：

```text
.codex/
  skills/
    workflow-skill-router/
      SKILL.md
```

如果你看到的是：

```text
.codex/
  skills/
    workflow-skill-router-blank/
      workflow-skill-router/
        SKILL.md
```

請把內層的 `workflow-skill-router/` 移到 `.codex/skills/`，再重新驗證。

## Validator 常見錯誤

### `Missing SKILL.md`

你驗證到錯誤 folder。請傳入直接包含 `SKILL.md` 的 folder：

```powershell
python $Validator (Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router")
```

### `Missing references/skill-tree.md`

Router folder 不完整。請重新解壓 `workflow-skill-router-blank.zip`，確認 `references/` folder 存在。

### `Missing references/routing-rules.md`

Router 還沒有 conflict handling 說明。請從 blank package 還原 `references/routing-rules.md`，再改造成自己的版本。

### `Route selects too many skills`

每條 route 應該只有一個 primary skill，最多三個 supporting skills。如果真的需要超過四個 skills，請拆成多個階段。

### Placeholder text remains

請把 template placeholders 換成你的真實 skill names、route categories 與 conflict rules。Validator 會期待公開前的 router 已經被改造成可用版本。

### Public-readiness audit 失敗

`validate-router.py` 檢查 router 結構。`audit-public-readiness.py` 檢查公開 repo 表面：文件、downloads、manifest、examples 與 stale assets。本機 private router 可以結構正確，但因為含有私人名稱或路徑而不適合公開。

## 還是卡住

開 issue 時請提供：

- 作業系統
- 你執行的完整 command
- 完整 validator output
- `workflow-skill-router/` 附近的解壓 folder tree

請不要貼私人專案名、客戶名、hostname、token 或內部 repository path。

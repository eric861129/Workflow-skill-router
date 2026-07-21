---
title: 發行流程
description: 建置可重現的產物、審查證據，並在不手動修改產物的前提下推進版本頻道。
---

## 1. 驗證原始碼

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest discover -s packages/router-core/tests -v
python -m unittest discover -s tests -v
python scripts/check-markdown-links.py .
```

## 2. 建置可重現產物

```powershell
$Version = (Get-Content -Raw -Encoding UTF8 release/version.json | ConvertFrom-Json).v2_version
$Output = Join-Path "dist" "release-$Version"
python scripts/build-release-artifacts.py --output-dir $Output --provenance-mode test --check-determinism
```

Builder 會讀取排序後的 allowlists、正規化 ZIP metadata、產生 checksums、SBOM、provenance 與 channel documents，並拒絕缺少或不安全的 path。應修改 source 或 allowlists；不得手動修補 generated archives。

只有 output directory 的既有項目全部屬於目前 generated manifest 時，才可重複使用該目錄。任何 stale、非預期、symlink 或未列入 manifest 的 path 都會在寫入前停止建置。請使用版本專屬目錄；builder 不會靜默清理混雜的 release generation。

## 3. 審查證據

- Contract fixtures 與 compatibility tests 均通過。
- 修正後的 Behavior evidence 已完成、成對且經過審查。
- Hard violations 為零。
- Public artifacts 不含 raw traces、local paths 或未受信任的 scores。
- 從解壓後 release assets 執行的 Plugin 與 Skill-only install smoke tests 均通過。

## 4. 透過受信任的發行 dispatch 推進

在發行 dispatch 前，先驗證 GitHub 的即時治理設定：

```powershell
python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router
```

此命令為唯讀，不會變更 GitHub 設定。通過僅確認擷取到的設定符合已納入版控的契約；它不是實際發行工作流程的演練，也不表示 GitHub Actions 的繞過權限已成功執行。失敗代表尚未證明遠端設定正確，必須阻擋本次發行清單。套用或變更遠端規則屬於需要權限的外部作業；請依照 `docs/governance/remote-release-governance.md` 的維護者指南處理。

`Release V2` workflow 只能由受信任的預設分支透過 `workflow_dispatch` 執行，並且必須輸入完全相同的確認字串 `CREATE_V2_RELEASE`。它會讀取受信任分支 `release/version.json` 的 `release_source_revision`，並在任何 preflight 開始前驗證該凍結 revision 可從受信任分支到達。

三平台 preflight 與 release build 都會 checkout 該凍結 revision，而不是 checkout 觸發 workflow 的分支。只有全部通過後，workflow 才會以 `GITHUB_TOKEN` 建立或驗證 annotated V2 tag、確認遠端 tag 解析為同一個凍結 revision、attest assets，並發布 GitHub prerelease。重試只在既有 tag 已解析為相同 revision 時才有效。

不得手動 push `v2.*` tag。請保護該 tag pattern，讓 release workflow 的 `GITHUB_TOKEN` 成為唯一授權建立者；否則儲存在凍結 source revision 的舊 workflow 可能會在受信任 dispatch 完成檢查前就先執行。此 repository contract 無法替你設定 GitHub 的 live ruleset，發行前必須另外確認。

`latest-v2` 可以指向已審查的 prerelease；在 V2 GA gates 全數通過前，`latest` 維持 V1.3.1。建立 tag、發布 GitHub Release、推進 channel、部署 Pages 與 push 都是個別授權的 actions；本機驗證不會自動執行它們。

## 5. 保留 V1 recovery

V1 仍可由不可變的 `v1.3.1` 取得。Legacy files 只有在 exact manifest review 與人工 cleanup gate 完成後，才會離開 primary branch。

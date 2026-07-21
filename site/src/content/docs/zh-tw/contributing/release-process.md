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
- Deterministic fixtures、reference driver 與 Pilot preparation 都不構成當期 behavior-model evidence。
- 只有 release 提出當期 behavior-model claims 時，Behavior evidence 才是必要 gate。需要此 gate 時，paired run 必須綁定 exact frozen candidate SHA、完成 trusted review，並在 promotion 前確認 hard violations 為零。
- Public artifacts 不含 raw traces、local paths 或未受信任的 scores。
- 從解壓後 release assets 執行的 Plugin 與 Skill-only install smoke tests 均通過。

## 4. 透過受信任的發行 dispatch 推進

在發行 dispatch 前，先驗證 GitHub 的即時治理設定：

```powershell
python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router
```

此命令為唯讀，不會變更 GitHub 設定。通過僅確認擷取到的設定符合已納入版控的契約；它不是實際發行工作流程的演練，也不表示 GitHub Actions 的繞過權限已成功執行。失敗代表尚未證明遠端設定正確，必須阻擋本次發行清單。套用或變更遠端規則屬於需要權限的外部作業；請依照 `docs/governance/remote-release-governance.md` 的維護者指南處理。

`Release V2` workflow 只能由受信任的預設分支透過 `workflow_dispatch` 執行，並且必須輸入完全相同的確認字串 `CREATE_V2_RELEASE`，但此字串不是發布 bypass。Workflow 會先 checkout 受信任的 dispatch revision，再從該 revision 的 `release/version.json` 同時讀取 `release_lifecycle` 與 `release_source_revision`。只有 `reviewed-attested-publishable` 可以執行；`prepared-local-candidate` 會讓 resolve-source job 在任何 preflight、建立 tag、asset attestation 或 GitHub Release 發布前失敗。凍結 source revision 也必須可從同一個受信任 checkout 到達。

未來 promotion 的固定程序如下：

1. **建置並凍結 candidate SHA。** 完成 source、release copies、版本化 notes、allowlists 與 deterministic assets，再記錄 candidate commit SHA。
2. **針對該 exact SHA 執行必要 evidence 與 review。** 對 frozen candidate 執行必要 CI、解壓後 asset smoke checks、governance review；只有當期 behavior-model claims 需要時，才對該 SHA 執行 paired Behavior gate，不得改對後續 branch head 執行。
3. **建立受信任的 metadata-only promotion commit。** 在預設分支更新 `release/version.json`，讓 `release_source_revision` 指向已審查 candidate SHA，並將 `release_lifecycle` 設為 `reviewed-attested-publishable`。不得把 metadata commit 當作 frozen source 重新建置或重新評估。
4. **Dispatch `Release V2`。** Workflow 會先以唯讀 Git object inspection 重新讀取 candidate metadata、release notes、builder 與 allowlists，之後才輸出 outputs 或啟動 preflight。

已審查且未變更的 candidate 可以直接進行步驟 3、4，不必重新建置或重新評估；前提是所有必要 evidence 仍綁定該 exact SHA。不得沿用另一個 source revision 的 evidence，或把 `CREATE_V2_RELEASE` 當成核准。

三平台 preflight 與 release build 都會 checkout 該凍結 revision，而不是 checkout 觸發 workflow 的分支。只有全部通過後，workflow 才會以 `GITHUB_TOKEN` 建立或驗證 annotated V2 tag、確認遠端 tag 解析為同一個凍結 revision、attest assets，並發布 GitHub prerelease。重試只在既有 tag 已解析為相同 revision 時才有效。

不得手動 push `v2.*` tag。請保護該 tag pattern，讓 release workflow 的 `GITHUB_TOKEN` 成為唯一授權建立者；否則儲存在凍結 source revision 的舊 workflow 可能會在受信任 dispatch 完成檢查前就先執行。此 repository contract 無法替你設定 GitHub 的 live ruleset，發行前必須另外確認。

`latest-v2` 可以指向已審查的 prerelease；在 V2 GA gates 全數通過前，`latest` 維持 V1.3.1。建立 tag、發布 GitHub Release、推進 channel、部署 Pages 與 push 都是個別授權的 actions；本機驗證不會自動執行它們。

## 5. 保留 V1 recovery

V1 仍可由不可變的 `v1.3.1` 取得。Legacy files 只有在 exact manifest review 與人工 cleanup gate 完成後，才會離開 primary branch。

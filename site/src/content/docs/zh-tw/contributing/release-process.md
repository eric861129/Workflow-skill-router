---
title: 發行流程
description: 建置 deterministic assets、審查證據，並在不手改 generated files 的前提下推進 channels。
---

## 1. 驗證原始碼

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest discover -s packages/router-core/tests -v
python -m unittest discover -s tests -v
python scripts/check-markdown-links.py .
```

## 2. 建置 deterministic assets

```powershell
$Version = (Get-Content -Raw -Encoding UTF8 release/version.json | ConvertFrom-Json).v2_version
$Output = Join-Path "dist" "release-$Version"
python scripts/build-release-artifacts.py --output-dir $Output --provenance-mode test --check-determinism
```

Builder 會讀取已排序的 allowlists、正規化 ZIP metadata、產生 checksums、SBOM、provenance 與 channel documents，並拒絕缺失或不安全的 paths。應修改 source 或 allowlists，不可直接 patch generated archives。

只有當既有 entry 全部屬於本次 generated manifest 時，才可重用 output directory。任何 stale、非預期、symlink 或其他未列入 manifest 的 path 都會在寫入前阻止 build。請使用版本專屬目錄；builder 不會靜默清理混合的 release generation。

## 3. 審查證據

- Contract fixtures 與 compatibility tests 全部通過。
- 修正後的 Behavior evidence 完整、成對且已審查。
- Hard violations 為零。
- Public artifacts 不含 raw traces、local paths 或 untrusted scores。
- Plugin 與純 SKILL 都通過從 release asset 解壓縮後的 install smoke test。

## 4. 明確推進版本

`latest-v2` 可以指向已審查的 prerelease；在 V2 GA gates 全數通過前，`latest` 維持 V1.3.1。建立 tag、發布 GitHub Release、推進 channel、部署 Pages 與 push 都是個別授權的 actions；本機驗證不會自動執行它們。

## 5. 保留 V1 recovery

V1 維持可從不可變的 `v1.3.1` 恢復。Legacy files 只有在 exact manifest review 與人工 cleanup gate 完成後才離開 primary branch。

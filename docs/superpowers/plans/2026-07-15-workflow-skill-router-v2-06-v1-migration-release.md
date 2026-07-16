# Workflow Skill Router V2 Migration and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破壞 V1 CLI／starter／fixture 的前提下，建立可重現、可稽核、跨平台的 V2 Skill 與 Plugin 發佈產物。

**Architecture:** Legacy entry points 透過 golden tests 與 versioned adapter 共存；單一 release builder 從 curated source allowlist 產生 deterministic ZIP、SHA-256、SPDX SBOM 與 channel manifests。V2 prerelease 走 `latest-v2`，既有 `latest` 與 `latest-v1` 繼續綁定不可變 V1.3.1 asset；任何 CI 或本機 release check 都只建立／驗證 artifacts，不 push、不 publish。

**Tech Stack:** Python 3.11+ standard library、`unittest`、ZIP/JSON/SHA-256/SPDX 2.3、GitHub Actions、Windows/macOS/Linux。

## Global Constraints

- 正式 V2 artifacts 僅為 `workflow-skill-router-skill-v<version>.zip` 與 `workflow-skill-router-plugin-v<version>.zip`；Plugin ZIP 只能從 repo 內 curated allowlist 建立，禁止打包任意本機 skill tree。
- `latest` 與 `latest-v1` 在 V2 GA 前指向 pinned V1.3.1；`latest-v2` 指向 V2 prerelease。不得把 prerelease 靜默取代 `latest`；這三個名稱與核准 spec 一致，不另建第二組 channel aliases。
- V1.3.1 必須存在 checked-in `downloads/archive/workflow-skill-router-skill-v1.3.1.zip` 與 `release/provenance/v1.3.1.json`。它只能從 annotated Git tag `v1.3.1` 的 peeled commit/tree 與該 tag 下的 `starter/workflow-skill-router/**` blobs 導入，禁止從目前 working tree/starter 重建或猜測。Provenance 固定 tag object、peeled commit/tree、path/blob manifest、archive SHA-256／size、builder revision、建立時間與 license；一般 build/check 只能驗證，不能覆寫 pinned asset。
- `starter/workflow-skill-router/` remains the V1 stable source；standalone V2 Skill source is `starter/v2/workflow-skill-router/` and must be byte-identical to the Plugin's copied SKILL tree。
- Legacy public scripts 維持 Python standard library、fresh clone 可執行；MCP SDK 只能存在 optional Plugin package。
- `package-downloads.py` 必須保留 `--skills-root`、private filters/environment contract 與「無 filter 拒絕打包」語意。
- ZIP entry 排序、timestamp、permission、path separator、UTF-8 與 JSON serialization 固定；同一 source tree 重建必須 byte-for-byte 相同。
- 本計畫只建立與驗證本機 artifacts；不 push tag、Git branch、release、channel 或網站。

---

## File Map

- `scripts/package-downloads.py`：修復 V1 blank package parity 與 manifest copy，保留既有 CLI。
- `scripts/build-release-artifacts.py`：V2 deterministic builder、checksums、SBOM、channel 與 `--check`。
- `scripts/smoke-release-assets.py`：驗證 archive/source parity、manifest、hash、SBOM 與 plugin contents。
- `release/version.json`、`release/*.schema.json`、`release/allowlists/*.json`：發佈來源與 machine-readable contracts。
- `release/provenance/v1.3.1.json`、`downloads/archive/workflow-skill-router-skill-v1.3.1.zip`：immutable V1 release evidence。
- `downloads/channels/*.json`、`downloads/release-manifest-v2.0.0-alpha.1.json`、`downloads/checksums.sha256`、`downloads/sbom/*.spdx.json`：generated release metadata。
- `packages/router-core/src/workflow_skill_router/compatibility/`：schema family 與 legacy adapter registry。
- `tests/test_release_artifacts.py`、`tests/test_legacy_cli_contract.py`、`tests/test_compatibility_adapters.py`：P0、determinism 與 CLI regression tests。
- `examples/template-skill-catalog/`：降級為不依賴本機 62-skill tree 的 legacy/tutorial snapshot。
- `.github/workflows/validate.yml`：generation check 與三平台 install/smoke matrix。

### Task 1: 修復 blank ZIP parity 與 manifest 文案矛盾

**Files:**
- Modify: `scripts/package-downloads.py`
- Modify: `scripts/smoke-release-assets.py`
- Create: `tests/test_package_downloads.py`
- Modify (generated): `downloads/workflow-skill-router-blank.zip`
- Modify (generated): `downloads/workflow-skill-router-template-manifest.md`

**Interfaces:**
- Consumes: `starter/workflow-skill-router/**`、既有 `package-downloads.py` CLI/environment/private-filter contract。
- Produces: `build_blank_archive(starter_root: Path, output: Path) -> None`；manifest section title 必須是 `Blank Router`；`assert_zip_matches_source(zip_path, source_root, allowlist) -> None`。

- [ ] **Step 1: 寫出目前會揭露 P0 的失敗測試**

```python
def test_blank_archive_skill_matches_starter_byte_for_byte(self):
    with ZipFile("downloads/workflow-skill-router-blank.zip") as archive:
        actual = archive.read("workflow-skill-router/SKILL.md")
    expected = Path("starter/workflow-skill-router/SKILL.md").read_bytes()
    self.assertEqual(actual, expected)

def test_generated_manifest_uses_smoke_contract_labels(self):
    text = package_downloads.manifest_text(self.fixture_catalog)
    self.assertIn("Blank Router", text)
    self.assertIn("Clean Template", text)
    self.assertIn("Full Template", text)
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest tests/test_package_downloads.py -v`

Expected: FAIL on blank `SKILL.md` byte parity and/or missing `Blank Router` label。

- [ ] **Step 3: 將 blank archive 改成唯一 starter source copy**

```python
BLANK_LABEL = "Blank Router"

def blank_entries(starter_root: Path) -> list[tuple[Path, str]]:
    return [(path, path.relative_to(starter_root.parent).as_posix())
            for path in sorted(starter_root.rglob("*")) if path.is_file()]

def manifest_text(catalog: PackageCatalog) -> str:
    return render_manifest([
        (BLANK_LABEL, catalog.blank),
        ("Clean Template", catalog.clean),
        ("Full Template", catalog.full),
    ])
```

不得從已存在 ZIP 回填 starter；一律由 starter 生成 archive，再由 smoke test 解壓比對 allowlisted source bytes。

- [ ] **Step 4: 重建並驗證 parity**

Run: `python scripts/package-downloads.py --skills-root sample-skills --exclude-prefix private- --private-marker PRIVATE`

Expected: exit 0，blank ZIP 與 manifest regenerated。

Run: `python -m unittest tests/test_package_downloads.py -v && python scripts/smoke-release-assets.py --downloads-dir downloads --work-dir .tmp/release-smoke`

Expected: PASS，三種 V1 archives 仍符合既有 smoke contract。

- [ ] **Step 5: Commit**

```bash
git add scripts/package-downloads.py scripts/smoke-release-assets.py tests/test_package_downloads.py downloads
git commit -m "fix(release): enforce blank archive source parity"
```

### Task 2: 建立 deterministic V2 artifacts、SHA-256、SBOM 與 channel manifests

**Files:**
- Create: `scripts/build-release-artifacts.py`
- Create: `release/version.json`
- Create: `release/release-manifest.schema.json`
- Create: `release/channel-manifest.schema.json`
- Create: `release/provenance/v1.3.1.json`
- Create: `release/allowlists/skill-package.json`
- Create: `release/allowlists/plugin-package.json`
- Create: `tests/test_release_artifacts.py`
- Create once, then verify as immutable: `downloads/archive/workflow-skill-router-skill-v1.3.1.zip`
- Create (generated): `downloads/channels/latest.json`
- Create (generated): `downloads/channels/latest-v2.json`
- Create (generated): `downloads/channels/latest-v1.json`
- Create (generated): `downloads/release-manifest-v2.0.0-alpha.1.json`
- Create (generated): `downloads/checksums.sha256`
- Create (generated): `downloads/sbom/workflow-skill-router-skill-v2.0.0-alpha.1.spdx.json`
- Create (generated): `downloads/sbom/workflow-skill-router-plugin-v2.0.0-alpha.1.spdx.json`
- Create (generated): `downloads/workflow-skill-router-skill-v2.0.0-alpha.1.zip`
- Create (generated): `downloads/workflow-skill-router-plugin-v2.0.0-alpha.1.zip`

**Interfaces:**
- Consumes: `starter/v2/workflow-skill-router/**` for the V2 Skill ZIP、`plugins/workflow-skill-router/**` including `runtime/workflow_skill_router.pyz` for the Plugin ZIP、`release/version.json` and curated allowlists。It must first verify canonical starter/Plugin SKILL parity and generated runtime `--check`；there is no `packages/router-core/dist/*.pyz` source。
- Produces: `import_pinned_v1_tag(repo_root, tag="v1.3.1") -> PinnedReleaseProvenance`（一次性、既有 target 時拒絕覆寫）；`build_release(repo_root: Path, output_root: Path, check: bool) -> ReleaseManifest`；`write_deterministic_zip(entries, output)`；`write_spdx_sbom(artifact, entries)`；CLI `python scripts/build-release-artifacts.py [--check] [--output-dir PATH] [--import-v1-tag v1.3.1]`。

- [ ] **Step 1: 寫 deterministic、allowlist 與 channels 失敗測試**

```python
def test_two_builds_are_byte_identical(self):
    first = build_release(ROOT, self.tmp / "a", check=False)
    second = build_release(ROOT, self.tmp / "b", check=False)
    self.assertEqual(first.artifact_hashes, second.artifact_hashes)

def test_plugin_archive_has_only_curated_entries(self):
    manifest = build_release(ROOT, self.tmp, check=False)
    names = zip_names(manifest.plugin_zip)
    self.assertEqual(names, set(load_allowlist("release/allowlists/plugin-package.json")))

def test_channels_do_not_promote_v2_prerelease_to_latest(self):
    channels = build_channels(load_versions())
    self.assertEqual(channels["latest"]["version"], "1.3.1")
    self.assertEqual(channels["latest-v1"]["version"], "1.3.1")
    self.assertEqual(channels["latest-v2"]["version"], "2.0.0-alpha.1")

def test_every_channel_resolves_to_an_immutable_verified_asset(self):
    for channel in build_channels(load_versions()).values():
        target = ROOT / channel["artifact_path"]
        self.assertTrue(target.is_file())
        self.assertEqual(channel["sha256"], sha256_file(target))
        digest_subject = {key: value for key, value in channel.items() if key != "manifest_entry_digest"}
        self.assertEqual(channel["manifest_entry_digest"], digest_manifest_entry(digest_subject))

def test_v1_pin_cannot_be_rewritten_by_normal_build(self):
    before = (ROOT / "downloads/archive/workflow-skill-router-skill-v1.3.1.zip").read_bytes()
    build_release(ROOT, self.tmp, check=False)
    self.assertEqual(before, (ROOT / "downloads/archive/workflow-skill-router-skill-v1.3.1.zip").read_bytes())

def test_v1_pin_is_derived_from_annotated_tag_not_current_starter(self):
    provenance = load_json("release/provenance/v1.3.1.json")
    self.assertEqual("v1.3.1", provenance["source_tag"])
    self.assertEqual(git_object_type("v1.3.1"), "tag")
    self.assertEqual(provenance["tag_object"], git_rev_parse("v1.3.1"))
    self.assertEqual(provenance["peeled_commit"], git_rev_parse("v1.3.1^{commit}"))
    self.assertEqual(provenance["source_tree"], git_rev_parse("v1.3.1^{tree}"))
    self.assertTrue(archive_matches_tag_blobs(PINNED_V1_ARCHIVE, provenance))

def test_import_refuses_to_overwrite_existing_v1_pin(self):
    with self.assertRaisesRegex(ReleaseError, "pinned_release_already_exists"):
        import_pinned_v1_tag(ROOT, "v1.3.1")
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest tests/test_release_artifacts.py -v`

Expected: FAIL with missing `build-release-artifacts.py`。

- [ ] **Step 3: 實作固定 metadata 與 release manifest**

```python
ZIP_TIME = (1980, 1, 1, 0, 0, 0)

def write_deterministic_zip(entries: list[PackageEntry], output: Path) -> None:
    # Store mode avoids platform/zlib-version-dependent compressed bytes.
    with ZipFile(output, "w", ZIP_STORED) as archive:
        for entry in sorted(entries, key=lambda item: item.archive_path):
            info = ZipInfo(entry.archive_path, ZIP_TIME)
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = ZIP_STORED
            archive.writestr(info, entry.source.read_bytes())
```

在此 task 第一次導入 V1.3.1 時，`--import-v1-tag v1.3.1` 先要求 tag object type=`tag`，記錄 tag object ID 與 peeled commit/tree，再以 `git ls-tree -r -z v1.3.1 -- starter/workflow-skill-router` 取得固定 path/blob IDs，逐檔以 `git cat-file blob <id>` 讀取歷史 bytes，最後交給同一個 `ZIP_STORED` writer；它不得讀 current working tree 的 starter。若 archive 或 provenance 任一已存在便拒絕覆寫。Provenance 與 archive 一起 commit；之後正常 build 把該 ZIP 視為 immutable input，先驗證 provenance、tag/blobs（當 Git metadata 可用）、archive hash／size與 entry allowlist。Release CI 使用 full history/tags，任何 mismatch 都 fail closed；一般 build/`--check` 沒有覆寫 V1 pin 的程式路徑。

`manifest_entry_digest` 的 digest subject 明確排除 `manifest_entry_digest` 欄位本身，只涵蓋 `schema_id`、schema version、channel、version、artifact path、SHA-256、size、release/provenance manifest path 與其 digest；writer 先 canonicalize/hash subject 再附加 digest，reader 以相同邊界重算，禁止自我引用。

Generated `downloads/release-manifest-v2.0.0-alpha.1.json` 每個 artifact 保存 filename、version、channel、sha256、size、source-tree digest、allowlist digest、builder revision、PYZ digest、MCP bundle digest、SBOM path、schema/plugin/core revision。Channel manifest 必須以相對 artifact path、SHA-256、size、release/provenance manifest path 與 `manifest_entry_digest` 綁定真實檔案。SPDX 2.3 `files` 為 archive entry 級 SHA-256；Plugin SBOM 另列 `@modelcontextprotocol/sdk@1.29.0`、`zod@4.1.12`、`esbuild@0.28.1` 的 package/version/license/checksum 與 archive `CONTAINS`/`DEPENDS_ON` relationships。`--check` 在 temp dir 重建 V2 outputs 並逐 byte 與 tracked output 比對，不修改 repo。

- [ ] **Step 4: 產生並檢查所有 release metadata**

Run once for the initial immutable import: `python scripts/build-release-artifacts.py --import-v1-tag v1.3.1`

Expected: annotated tag、peeled commit/tree、blob manifest 與 deterministic archive 已建立；若 target 已存在則拒絕覆寫。

Run: `python scripts/build-release-artifacts.py`

Expected: exit 0，V1 pin 驗證通過，產生兩個 versioned V2 ZIP、`latest|latest-v2|latest-v1` 三個 channel manifests、versioned release manifest、checksums 與兩份 SPDX SBOM。

Run: `python scripts/build-release-artifacts.py --check && python -m unittest tests/test_release_artifacts.py -v`

Expected: PASS；任一 source/zip/manifest/SBOM drift 都使 `--check` exit 1。

- [ ] **Step 5: Commit**

```bash
git add scripts/build-release-artifacts.py release tests/test_release_artifacts.py downloads
git commit -m "feat(release): build deterministic versioned artifacts"
```

### Task 3: 凍結 V1 CLI 並加入 versioned compatibility registry

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/compatibility/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/compatibility/registry.py`
- Create: `packages/router-core/src/workflow_skill_router/compatibility/legacy_v1.py`
- Create: `tests/test_compatibility_adapters.py`
- Read/verify: `packages/router-core/tests/compat/golden/legacy-cli-v1.json`
- Read/verify: `packages/router-core/tests/compat/test_legacy_cli_goldens.py`

**Interfaces:**
- Consumes: legacy artifact families、spec 22.2 exact commands，以及 plan 01 已凍結的 `legacy-cli-v1.json`；不得建立第二份 golden truth。
- Produces: `AdapterKey(schema_id, schema_version, artifact_kind)`；`AdapterRegistry.resolve(key) -> ArtifactAdapter`；legacy aliases and suite-local collision map。Subprocess contract 持續由 plan 01 的單一 golden harness 驗證。

- [ ] **Step 1: 寫完整 CLI contract 與 ambiguous identity 失敗測試**

```python
def test_ambiguous_alias_is_not_resolved_by_provider_order(self):
    with self.assertRaisesRegex(AdapterViolation, "ambiguous_alias"):
        self.registry.resolve_capability_alias("shared-name")
```

- [ ] **Step 2: 驗證基準先抓到未建 registry／golden**

Run: `python -m unittest discover -s packages/router-core/tests/compat -p "test_legacy_cli_goldens.py" -v && python -m unittest tests/test_compatibility_adapters.py -v`

Expected: plan 01 golden tests PASS；adapter test FAIL with missing compatibility registry。

- [ ] **Step 3: 實作 family-aware registry 與薄 shim**

```python
@dataclass(frozen=True)
class AdapterKey:
    schema_id: str
    schema_version: str
    artifact_kind: str

class AdapterRegistry:
    def resolve(self, key: AdapterKey) -> ArtifactAdapter:
        try:
            return self._adapters[key]
        except KeyError as error:
            raise AdapterViolation(f"unsupported_artifact:{key}") from error
```

Compatibility adapter 以 subprocess 呼叫既有 legacy scripts 或直接讀取其 artifacts，不讓 legacy scripts import `packages/router-core`。所有 scripts 保持原 argparse、env、ordering、stdout/stderr、exit code 與 generated shape；`--strict` 與 `--fail-on-violations` 原 exit behavior 由 golden tests 鎖定。只有 V2 adapter 輸出附加 `tier=T0`、`evidence_class=contract-only`，不改寫 V1 CLI output。

- [ ] **Step 4: 跑 legacy 與新 registry regression**

Run: `python -m unittest discover -s packages/router-core/tests/compat -p "test_legacy_cli_goldens.py" -v && python -m unittest tests/test_compatibility_adapters.py tests/test_evaluate_routing.py tests/test_route_cases.py tests/test_scan_skills.py -v`

Expected: PASS；V1 artifacts 不會因只有 `schema_version` 而誤判成 V2。

- [ ] **Step 5: Commit**

```bash
git add packages/router-core/src/workflow_skill_router/compatibility tests/test_compatibility_adapters.py
git commit -m "feat(compat): preserve v1 cli and artifact contracts"
```

### Task 4: 將 reference catalog 降級為可重現 legacy/tutorial

**Files:**
- Modify: `examples/template-skill-catalog/README.md`
- Modify: `examples/template-skill-catalog/SKILL.md`
- Modify: `examples/template-skill-catalog/references/routing-rules.md`
- Modify: `examples/template-skill-catalog/references/sample-routes.md`
- Modify: `examples/template-skill-catalog/references/skill-tree.md`
- Create: `examples/template-skill-catalog/references/capability-catalog.example.json`
- Create: `tests/test_template_catalog.py`

**Interfaces:**
- Consumes: 只使用 repo 內 checked-in tutorial metadata；不得讀取 `C:\Users\...\.codex\skills` 或假設 62 個本機 skills。
- Produces: `capability-catalog.example.json` with `schema_id="workflow-skill-router/legacy-tutorial-catalog"`；文件明示此目錄不是 runtime discovery snapshot、不是完整 V2 router。

- [ ] **Step 1: 寫 fresh clone 可重現性失敗測試**

```python
def test_tutorial_catalog_references_only_checked_in_capabilities(self):
    catalog = json.loads(Path(CATALOG).read_text("utf-8"))
    referenced = collect_documented_capability_ids(Path("examples/template-skill-catalog"))
    self.assertLessEqual(referenced, {item["canonical_id"] for item in catalog["capabilities"]})
    self.assertNotRegex(json.dumps(catalog), r"[A-Za-z]:\\Users\\|/Users/|/home/")
```

- [ ] **Step 2: 驗證舊 catalog 依賴缺失 skills**

Run: `python -m unittest tests/test_template_catalog.py -v`

Expected: FAIL，列出未在 repo catalog 定義的本機 skill IDs。

- [ ] **Step 3: 改寫為小型 metadata tutorial**

`capability-catalog.example.json` 僅保留文件示範需要的 6–10 個虛構／public sample capabilities，所有 route example 只引用該 catalog；README 首段標示 `Legacy/tutorial example — not runtime discovery and not real-model evidence`。

- [ ] **Step 4: 驗證無本機路徑與無未解析 capability**

Run: `python -m unittest tests/test_template_catalog.py -v && python scripts/audit-public-readiness.py .`

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add examples/template-skill-catalog tests/test_template_catalog.py
git commit -m "docs(example): make legacy catalog reproducible"
```

### Task 5: 三平台 CI 與 release gate

**Files:**
- Modify: `.github/workflows/validate.yml`
- Modify: `.github/workflows/deploy-site.yml`
- Create: `tests/test_installation_smoke.py`
- Modify: `scripts/smoke-release-assets.py`

**Interfaces:**
- Consumes: `build-release-artifacts.py --check`、Skill/Plugin ZIP、Python 3.11 launcher、Node MCP bundle、pure SKILL fallback。
- Produces: matrix `ubuntu-latest|macos-latest|windows-latest`，驗證 unzip/install、MCP handshake/SQLite migration、MCP unavailable fallback 與 UTF-8；deploy job 只有在 validation workflow 成功後才可執行。

- [ ] **Step 1: 寫 archive install/fallback smoke 測試**

```python
def test_skill_and_plugin_archives_install_without_repo_paths(self):
    for artifact in release_artifacts():
        install = unpack_to_temp(artifact)
        self.assertTrue(validate_installed_artifact(install))

def test_missing_mcp_runtime_falls_back_without_lowering_risk(self):
    result = run_installed_router(disable_mcp=True, request_fixture="r3-explicit-skill")
    self.assertEqual(result.runtime_mode, "skill-only")
    self.assertEqual(result.conformance, "skill-only-fallback")
    self.assertTrue(result.requires_runtime_approval)
```

- [ ] **Step 2: 驗證本機 smoke test 先紅燈**

Run: `python -m unittest tests/test_installation_smoke.py -v`

Expected: FAIL until versioned archives and launchers exist。

- [ ] **Step 3: 加入 generation gate 與 OS matrix**

```yaml
release-artifacts:
  strategy:
    fail-fast: false
    matrix:
      os: [ubuntu-latest, macos-latest, windows-latest]
  runs-on: ${{ matrix.os }}
  steps:
    - uses: actions/checkout@v6
      with: { fetch-depth: 0 }
    - uses: actions/setup-python@v6
      with: { python-version: "3.11" }
    - uses: actions/setup-node@v6
      with: { node-version: "24" }
    - run: python scripts/build-release-artifacts.py --check
    - run: python -m unittest tests/test_installation_smoke.py -v
```

Deploy workflow 必須以 `workflow_run` 或 required validation job 依賴 validation success；validation 不執行 `git push`、GitHub Release 或 deploy commands。

- [ ] **Step 4: 跑本機完整 release gate**

Run: `python scripts/build-release-artifacts.py --check && python scripts/smoke-release-assets.py --downloads-dir downloads --work-dir .tmp/release-smoke && python -m unittest discover -s tests -v`

Expected: PASS；tracked artifacts 無 drift，V1 與 V2 install smoke 都通過。

- [ ] **Step 5: Commit**

```bash
git add .github/workflows tests/test_installation_smoke.py scripts/smoke-release-assets.py
git commit -m "ci: verify release artifacts on three platforms"
```

## Plan Verification

- [ ] `python scripts/package-downloads.py ...` 後立即執行 `python scripts/build-release-artifacts.py --check`，Expected: PASS，避免 builder 再次製造 manifest 矛盾。
- [ ] 對兩個 V2 ZIP 各重建兩次並執行 `Get-FileHash -Algorithm SHA256`（Windows）或 `sha256sum`（Linux），Expected: 相同 source 產生相同 hash。
- [ ] `python -m unittest discover -s tests -v`，Expected: V1 legacy、release、installation tests 全部 PASS。
- [ ] `git status --short`，Expected: 只有計畫內生成／修改的 release files；不含私有 skill、credential、absolute user path。
- [ ] 停在本機已驗證 commits；不得執行 push、tag、GitHub Release、channel upload 或網站 publish。

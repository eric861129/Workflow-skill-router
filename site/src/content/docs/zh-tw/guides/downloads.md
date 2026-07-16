---
title: 安裝模式與 Release Assets
description: 選擇符合 Codex Host 真實能力邊界的 V2 runtime，再安裝或檢查正確 package。
---

## 選擇你的 V2 安裝模式

Workflow Skill Router 只有一個 policy core，但有多種 runtime boundary。應依 Host 真正能提供的 authority 選擇，而不是挑功能清單最長的模式。

<div class="wsr-download-picker" aria-label="V2 安裝模式比較">
  <article class="wsr-download-card wsr-download-card-featured">
    <div>
      <span class="wsr-download-kicker">主要安裝方式</span>
      <h3>Bundled Plugin + MCP</h3>
      <p>需要 durable local R0 planning、runtime readiness、typed MCP result，以及 fail-closed Host handoff 時，使用 Codex Plugin。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Local-ready</dt><dd><code>plan_work</code> 與 <code>get_router_status</code></dd></div>
      <div><dt>Runtime label</dt><dd><code>bundled-local-r0</code></dd></div>
      <div><dt>系統需求</dt><dd>Codex Plugin/MCP、Python 3.11+、Node.js 24+</dd></div>
    </dl>
    <a class="wsr-download-button" href="/Workflow-skill-router/zh-tw/guides/install-plugin/">安裝 Plugin + MCP</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Host integration</span>
      <h3>Verified-host integration</h3>
      <p>Scheduler、compare-and-swap state、受保護 route validation、gates 與 Goal progression，只能透過 Host 驗證過的 ports 與 receipts 加入。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>最適合</dt><dd>Codex 或平台整合者</dd></div>
      <div><dt>Authority</dt><dd>由 Host 所有，不從本機檔案推測</dd></div>
      <div><dt>Fallback</dt><dd>Typed <code>capability-unavailable</code></dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="/Workflow-skill-router/zh-tw/concepts/managed-goals/">檢查 Host boundary</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">授權後的 evaluation</span>
      <h3>Configured evaluation adapter</h3>
      <p>透過 server-configured executable 執行 fresh Behavior 或 Outcome attempts。Model input 無法選擇 executable、quota 或 publication status。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>最適合</dt><dd>執行 reviewed benchmark 的 maintainers</dd></div>
      <div><dt>需要</dt><dd>Trusted adapter configuration 與明確 quota authorization</dd></div>
      <div><dt>發布狀態</dt><dd>取得 attestation 前維持 review-required</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="/Workflow-skill-router/zh-tw/concepts/evaluation-evidence/">閱讀 evidence contract</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Instruction-only fallback</span>
      <h3>純 SKILL</h3>
      <p>Host 無法執行 Plugin 或 MCP 時，載入 V2 routing instructions。Explicit Skill Lock 與使用揭露仍存在，但不提供 durable runtime guarantees。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Runtime label</dt><dd><code>skill-only-fallback</code></dd></div>
      <div><dt>包含</dt><dd>Canonical <code>SKILL.md</code>、references、agent metadata</dd></div>
      <div><dt>不包含</dt><dd>Durable resume、跨程序 CAS、sealed instrumentation</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="/Workflow-skill-router/zh-tw/guides/install-skill/">只使用 SKILL</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Contributors 與 integrators</span>
      <h3>Source checkout</h3>
      <p>需要修改 policy core、transport、deterministic builders、文件或 Host adapter 時使用 source。Generated release files 不可手動編輯。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>主要來源</dt><dd>Git repository 與 pinned dependency locks</dd></div>
      <div><dt>Build output</dt><dd>Ignored <code>dist/release/</code></dd></div>
      <div><dt>驗證</dt><dd>Core、MCP、docs、site、install、SBOM、provenance</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="https://github.com/eric861129/Workflow-skill-router">在 GitHub 查看 source</a>
  </article>
</div>

## Marketplace 安裝

不可變 beta tag 尚未發布前，使用 contributor checkout：

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
```

`v2.0.0-beta.1` 存在後，pin marketplace snapshot：

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.0-beta.1
codex plugin add workflow-skill-router@workflow-skill-router
```

## 離線檢查 assets

以下 beta assets 只有在 GitHub prerelease 發布後才會存在。它們是 release assets，不是可變動的 `raw/main/downloads` 檔案。

- [Plugin ZIP：`workflow-skill-router-plugin-v2.0.0-beta.1.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.0-beta.1/workflow-skill-router-plugin-v2.0.0-beta.1.zip)
- [純 SKILL ZIP：`workflow-skill-router-skill-v2.0.0-beta.1.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.0-beta.1/workflow-skill-router-skill-v2.0.0-beta.1.zip)
- [所有 Releases](https://github.com/eric861129/Workflow-skill-router/releases)

ZIP 用於離線檢查與 fallback installation。使用前必須驗證發布的 checksums、SBOM 與 provenance；不可把本機 prerelease build 當成已發布 asset。

## 安裝後驗證

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

預期 bundled result：`runtime_profile` 是 `bundled-local-r0`、telemetry disabled，而且只有 `plan_work` 與 `get_router_status` 是 local-ready。接著進入 [V2 快速開始](/Workflow-skill-router/zh-tw/guides/quickstart/)。

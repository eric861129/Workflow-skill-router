---
title: 安裝模式與 Release Assets
description: 比較 Plugin + MCP 與純 SKILL，選擇適合目前 Codex 環境的安裝方式。
---

## 選擇你的 V2 安裝模式

一般使用者若要完整功能，直接選 Plugin + MCP；目前環境不能載入 Plugin/MCP 時，再選純 SKILL。其他模式主要提供給平台整合者與評測維護者。

這些模式共用同一套 policy core，但 runtime boundary 不同。Router 只會使用 Host 真正提供的權限與能力，不會因為安裝了檔案就宣稱所有功能都可用。

<div class="wsr-download-picker" aria-label="V2 安裝模式比較">
  <article class="wsr-download-card wsr-download-card-featured">
    <div>
      <span class="wsr-download-kicker">主要安裝方式</span>
      <h3>Bundled Plugin + MCP</h3>
      <p>一般 Codex 使用者建議選這個模式。它會保存本機規劃與輔助技能同意狀態，並清楚回報哪些工具可直接執行。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Local-ready</dt><dd><code>plan_work</code>、<code>propose_support_consent</code>、<code>transition_support_consent</code> 與 <code>get_router_status</code></dd></div>
      <div><dt>Runtime label</dt><dd><code>bundled-local-r0</code></dd></div>
      <div><dt>系統需求</dt><dd>Codex Plugin/MCP、Python 3.11+、Node.js 24+</dd></div>
    </dl>
    <a class="wsr-download-button" href="/Workflow-skill-router/zh-tw/guides/install-plugin/">安裝 Plugin + MCP</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Host integration</span>
      <h3>Verified-host integration</h3>
      <p>只有把 Router 接進自有平台的整合者才需要此模式。Scheduler、受保護的 route validation、gates 與 Goal progression，必須由 Host 提供可驗證的 ports 與 receipts。</p>
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
      <p>只有執行正式模型評測的維護者才需要設定此 adapter。它透過伺服器預先設定的 executable 執行 fresh Behavior 或 Outcome attempts，模型輸入不能自行選擇額度或發布狀態。</p>
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
      <p>環境不能載入 Plugin/MCP 時選這個模式。它仍會尊重使用者指定的 SKILL 並揭露使用情況，但不提供可持久化的 Runtime 保證。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>Runtime label</dt><dd><code>skill-only-fallback</code></dd></div>
      <div><dt>目前 source 包含</dt><dd><code>SKILL.md</code>、<code>assets/personal-routing-profile.example.json</code>、<code>assets/workspace-routing-profile.example.json</code>、<code>references/evaluation-boundary.md</code>、<code>references/goal-protocol.md</code>、<code>references/personal-routing-profiles.md</code> 與 <code>references/routing-protocol.md</code></dd></div>
      <div><dt>不包含</dt><dd>Durable resume、跨程序 CAS、sealed instrumentation</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="/Workflow-skill-router/zh-tw/guides/install-skill/">只使用 SKILL</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Contributors 與 integrators</span>
      <h3>Source checkout</h3>
      <p>需要修改 Router 原始碼、文件或 Host adapter 時才使用 source checkout。Generated release files 不可手動編輯。</p>
    </div>
    <dl class="wsr-download-specs">
      <div><dt>主要來源</dt><dd>Git repository 與 pinned dependency locks</dd></div>
      <div><dt>Build output</dt><dd>Ignored <code>dist/release/</code></dd></div>
      <div><dt>驗證</dt><dd>Core、MCP、docs、site、install、SBOM、provenance</dd></div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="https://github.com/eric861129/Workflow-skill-router">在 GitHub 查看 source</a>
  </article>
</div>

`v2.0.2` 的 Plugin 與純 SKILL 套件都包含 strict Personal 與 Workspace Routing Profile 範例。Skill-only 只有在 Host 授權 filesystem access 時，才能讀取固定的本機 Profile 路徑。

## Marketplace 安裝

一般使用者請固定安裝已發布且不可變的 marketplace snapshot：

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.2
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

需要修改 Router 的貢獻者，才使用 repository checkout：

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
```

## 離線檢查 assets

請使用不可變的 `v2.0.2` GitHub Release assets，不要從可變動的 `raw/main/downloads` 檔案安裝。

- [Plugin ZIP：`workflow-skill-router-plugin-v2.0.2.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.2/workflow-skill-router-plugin-v2.0.2.zip)
- [純 SKILL ZIP：`workflow-skill-router-skill-v2.0.2.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.2/workflow-skill-router-skill-v2.0.2.zip)
- [所有 Releases](https://github.com/eric861129/Workflow-skill-router/releases)

ZIP 用於離線檢查與 fallback installation。使用前必須驗證發布的 checksums、SBOM 與 provenance；不可把本機 prerelease build 當成已發布 asset。

## 安裝後驗證

Marketplace 安裝先確認 Codex 看得到 Plugin，重新啟動 Codex，再開新任務要求顯示 Workflow Skill Router 狀態：

```powershell
codex plugin list
```

解壓縮的 Plugin package 請在 Plugin 根目錄執行：

```powershell
python runtime/workflow_skill_router.pyz doctor
```

Repository contributor 則在 repository root 執行：

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

預期 bundled result：`runtime_profile` 是 `bundled-local-r0`、telemetry disabled，而且 `plan_work`、`propose_support_consent`、`transition_support_consent` 與 `get_router_status` 都是 local-ready。接著進入 [V2 快速開始](/Workflow-skill-router/zh-tw/guides/quickstart/)。

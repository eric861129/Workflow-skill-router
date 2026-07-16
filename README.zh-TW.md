# Workflow Skill Router V2 — 繁體中文

Workflow Skill Router 是 Codex 的 runtime-aware 路由與編排層。它會把工作分成 **Single**、**Phased** 或 **Managed Goal**，在每個 Phase／Work Item 重新判斷能力，同時保留使用者指定 SKILL 的鎖定與同意邊界。

## 快速開始

- **純 SKILL：**安裝 [`starter/v2/workflow-skill-router`](starter/v2/workflow-skill-router)。系統會明示 `skill-only-fallback`；durable resume、CAS、完整 drift detection 與 activation instrumentation 都不可觀測。
- **Plugin/MCP：**使用 [`downloads/`](downloads/) 的 V2 Plugin。十個 typed tools 提供 runtime sync、route、Phase/Goal state、真實模型評測與安全匯出。只有 host handshake 與 bound-content preflight 都驗證後才可稱為 `hybrid-full`。

小型、中型與 Goal 任務都支援 Explicit Skill Lock。Router 想加入輔助能力時，必須先說明用途、scope、拒絕限制與 context cost；使用者拒絕後不得讀取或啟用。R2/R3 仍由 host approval 控制。

## 評測證據

既有 80 案例是 **Tier 0 Contract**，不是模型實跑。Behavior／Outcome 至少要三次 fresh attempt、隔離答案與 paired comparison。沒有 adapter 時是 `manual-required`；沒有可信任的人工作業驗證時是 `review-required`，公開 artifact 不顯示分數。

## 版本與文件

`latest`／`latest-v1` 固定 V1.3.1，`latest-v2` 才是 V2 alpha。請看 [V2 架構](docs/v2-architecture.zh-TW.md)、[升級與回復](docs/v1-to-v2-upgrade.zh-TW.md) 與 [完整驗證](README.md#validation)。

---
title: V2 Roadmap
description: 以可驗證的證據，追蹤從 alpha 到 GA 的里程碑。
---

## Alpha — contract 與 local control plane

- Runtime Capability Discovery 與 merge authority
- Single、Phased、Managed Goal policy
- Explicit Skill Lock 與 consent semantics
- Phase/Goal state machines 與 durable event contracts
- Plugin packaging、MCP schemas、本機 R0 `plan_work` 與 status
- Sealed subprocess evaluation adapter 與 reference fixtures
- 可檢查的 Flight Recorder

## Beta 2.0.0-beta.1 — 已完成

- [x] 已發布不可變的 `v2.0.0-beta.1` marketplace snapshot

## Beta 2.0.0-beta.2 — release candidate

- [x] 加入 Personal 與 Workspace Routing Profiles 及套件範例
- [x] 修正 junction、symlink、migration 與 evidence labeling 缺口
- [x] 讓凍結 source revision 的 Windows、macOS、Linux CI 全部通過
- [ ] 發布 prerelease，且只移動 `latest-v2`
- [x] 已在明確 quota authorization 下完成修正後的 36-attempt Behavior smoke
- [x] 已審查 paired results，只發布有 attestation 且已去識別化的 evidence
- [x] 已在 Windows、macOS、Linux 驗證 Plugin 與純 SKILL 的 release-archive contracts

## 下一個 beta 里程碑

- [ ] 在 fixtures 以外實際演練 verified Host scheduler/evidence integration

## GA — promotion gate

- [ ] 通過 13 案例、78-attempt／96-model-turn paired Behavior suite
- [ ] 維持零 hard violations
- [ ] 完成 security review、dependency/SBOM checks、docs parity 與 release rehearsal
- [ ] 透過人工 manifest gate 移除已審查的 V1 public clutter
- [ ] 只有全部 required gates 通過後才推進 `latest`

Roadmap 不是 availability 宣告；目前 readiness 仍以 generated runtime matrix 為準。

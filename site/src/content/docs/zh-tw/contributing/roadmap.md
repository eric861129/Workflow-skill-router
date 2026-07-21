---
title: V2 路線圖
description: 以可驗證證據追蹤從 alpha 到 GA 的里程碑。
---

## Alpha — 合約與本機控制平面

- Runtime Capability Discovery 與 merge authority
- Single、Phased、Managed Goal policy
- Explicit Skill Lock 與 consent semantics
- Phase／Goal state machine 與 durable event contract
- Plugin packaging、MCP schemas、本機 R0 `plan_work` 與 status
- Sealed subprocess evaluation adapter 與 reference fixtures
- 可檢視的 Flight Recorder

## Beta 2.0.0-beta.1 — 已完成

- [x] 發布不可變的 `v2.0.0-beta.1` marketplace snapshot

## Beta 2.0.0-beta.2 — 已完成

- [x] 加入 Personal 與 Workspace Routing Profiles 及套件範例
- [x] 關閉 junction、symlink、migration 與 evidence labeling 缺口
- [x] 在凍結的 source revision 通過 Windows、macOS、Linux CI
- [x] 發布 prerelease，且只更新 `latest-v2`
- [x] 經明確額度授權完成修正版 36-attempt Behavior smoke
- [x] 審查 paired results，只發布已 attested 的 sanitized evidence
- [x] 在 Windows、macOS、Linux 驗證 Plugin 與 Skill-only release archive

## Beta 2.0.0-beta.3 — 已完成

- [x] 以 scoped dependency boundary 關閉 Lighthouse／OpenTelemetry 開發工具 advisory
- [x] 移除 Pages deployment 的 privileged `workflow_run` checkout
- [x] 將 Pages 發布綁定至已驗證的 trusted `main` revision
- [x] 發布新的 immutable prerelease，且只更新 `latest-v2`

## Beta 2.0.0-beta.4 — 本機候選版本

- [x] 加入 Single、Phased、Managed Goal 的無 hint 可解釋分類
- [x] 加入 deterministic Profile explain／lint 與 Contract 2.3.0 Profile miss 案例
- [x] 封存 attempt nonce、tool inventory、instruction digest、public case digest 與 model version
- [x] 在本機準備 deterministic Plugin 與 Skill-only release artifacts
- [ ] 取得 36 attempts／42 model turns 的明確模型額度授權
- [ ] 人工審查 sanitized evidence、attest 零 hard violations，並發布 immutable prerelease

Reference-driver 只驗證離線合約；it does not prove real-model behavior。在剩餘審查與發布 gate 完成前，beta.3 仍是最新已發布的 V2 snapshot。

## 下一個 Beta 里程碑

- [ ] 在 fixtures 之外，驗證一套 Host scheduler／evidence integration

## GA — promotion gate

- [ ] 通過 13-case、78-attempt、96-model-turn paired Behavior suite
- [ ] 維持零 hard violations
- [ ] 完成 security review、dependency／SBOM checks、雙語文件一致性與 release rehearsal
- [ ] 依已審查的人工 manifest gate 移除 V1 公開介面的剩餘雜訊
- [ ] 所有必要 gate 通過後，才把 `latest` 提升至 V2

路線圖項目不是 availability claim；目前 readiness 仍以 generated runtime matrix 為準。

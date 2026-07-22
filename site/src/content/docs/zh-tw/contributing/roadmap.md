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

## Beta 2.0.0-beta.4 — 歷史準備工作

- [x] 加入 Single、Phased、Managed Goal 的無 hint 可解釋分類
- [x] 加入 deterministic Profile explain／lint 與 Contract 2.3.0 Profile miss 案例
- [x] 封存 attempt nonce、tool inventory、instruction digest、public case digest、model version 與私有 scoring-spec digest
- [x] 在本機準備 deterministic Plugin 與 Skill-only release artifacts
- [ ] 取得 36 attempts／42 model turns 的明確模型額度授權
- [ ] 人工審查 sanitized evidence、attest 零 hard violations，並發布 immutable prerelease

Reference-driver 只驗證離線合約；它無法證明真實模型的行為。這段 beta.4 歷史準備工作並不是已發布版本。

## Beta 2.0.0-beta.5 — 已準備 candidate

- [x] 加入 Router-owned Local Work Loop：將 `get_next_work`、`record_work_event` 與 `evaluate_gate` 限定為 `conditional-local` 操作
- [x] 保留 Explicit Skill Lock、scoped consent、Native Goal 保護與 fail-closed authority separation
- [x] 加入 Host Integration Kit、reference adapter、capability manifest 與跨平台 conformance suite
- [x] 凍結二十個本機真實任務的 Pilot protocol、verified-Host lane 與 semantic-recommender decision gate
- [x] 建立 prepared local candidate，同時讓 `latest` 維持 V1.3.1、已發布的 `latest-v2` 維持 beta.3
- [ ] 執行並獨立審查至少 20 個真實本機 Pilot 任務
- [ ] 完成真實 verified-Host Pilot，或發布經審查的 `capability-unavailable` evidence
- [ ] 在執行新的 36 attempts／42 model turns behavior-model run 前取得明確授權
- [ ] 審查 sanitized evidence、attest exact frozen candidate SHA，並發布 immutable prerelease

prepared beta.5 candidate 尚未發布。只有在 evidence 與 review 完成後，後續受信任的 metadata-only promotion commit 才能重綁它的 `release_source_revision`。

## 下一個 Beta 里程碑

- [ ] 在 fixtures 之外，驗證一套 Host scheduler／evidence integration

## GA — promotion gate

- [ ] 通過 13-case、78-attempt、96-model-turn paired Behavior suite
- [ ] 維持零 hard violations
- [ ] 完成 security review、dependency／SBOM checks、雙語文件一致性與 release rehearsal
- [ ] 依已審查的人工 manifest gate 移除 V1 公開介面的剩餘雜訊
- [ ] 所有必要 gate 通過後，才把 `latest` 提升至 V2

路線圖項目不是 availability claim；目前 readiness 仍以 generated runtime matrix 為準。

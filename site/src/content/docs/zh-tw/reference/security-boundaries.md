---
title: 安全邊界
description: 分離 instruction consent、runtime authority、side effects 與 evaluation trust。
---

## 四個獨立決策

1. **Install：**把 Plugin 或 SKILL 放到 Codex 可以發現的位置。
2. **Activate instructions：**同意在宣告範圍內讀取或使用某個 SKILL。
3. **Authorize runtime：**透過 Host 允許 tools、files、network、subprocesses 或 secrets。
4. **Authorize side effects：**核准 deployment、messages、production changes、publication 或其他重大操作。

任何一個決策都不會自動包含下一個。

## Fail-closed 規則

- Agent observations 不能產生 Host authority。
- Runtime cache 不能把 unavailable capability 升級為可用。
- Protected route activation 需要 current snapshot、policy、consent、lease 與 bound-content receipt。
- Lease 綁定 purpose/scope、只能使用一次，並受 freshness 限制。
- Side effects 不明時阻擋驗證。
- Native Goal mutation 仍由 Host 所有。
- Evaluation executable 由 server 設定；model input 無法選擇。
- Raw model traces 與 local paths 不得進入 public artifacts。

## Risk

R0 local planning 可在 bundled control plane 執行。R1 需要更嚴格的 runtime validation；R2/R3 仍受 Codex sandbox、approval 與 permission boundaries 控制。較低的 routing risk label 不會降低 Host 自身的風險判斷。

## 回報弱點

依照 [SECURITY.md](https://github.com/eric861129/Workflow-skill-router/blob/main/SECURITY.md) 回報。不要在 public issue 放入 secrets、private repository data 或 exploit details。

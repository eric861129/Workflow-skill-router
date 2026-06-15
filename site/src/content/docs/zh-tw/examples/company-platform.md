---
title: 公司平台範例
description: 用匿名化企業平台情境展示真實 workflow 複雜度。
---

這個範例模擬一個公司平台：包含 backend services、customer portal、internal admin、文件、CI/CD、RBAC 與 incident workflow。

## 適合對象

- SaaS platforms
- internal operations systems
- customer portals
- revenue platforms
- 有 live data 與 deployment gates 的團隊

## Sample route

```text
Route: Sync / Backend to frontend > API schema and client update > Customer portal
Use SKILL: platform-api-contract, client-generation, portal-frontend-core, frontend-debugging
Reason: platform-api-contract protects the schema; client-generation updates types; portal-frontend-core aligns app boundaries; frontend-debugging verifies rendered behavior.
```

## 為什麼重要

這條 route 可以避免 Agent 在 API contract 還沒穩定時，就直接衝去改前端。它也會把 browser verification 保留在範圍內，因為 generated clients 即使型別正確，仍然可能在 runtime 出錯。

## Source

請看：

```text
examples/company-platform-sanitized/
```

---
title: Privacy-first Analytics
description: 文件站如何追蹤轉換，同時不直接追蹤 GitHub README views。
---

Workflow Skill Router 使用 Plausible-compatible analytics hook，預設關閉。沒有設定 public environment variables 時，站台仍可正常 build，而且不會載入 analytics script。

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `PUBLIC_ANALYTICS_PROVIDER` | Yes | 設為 `plausible` 才啟用 analytics。 |
| `PUBLIC_PLAUSIBLE_DOMAIN` | Yes | Plausible 或相容服務中設定的 domain。 |
| `PUBLIC_PLAUSIBLE_SCRIPT_URL` | No | 覆寫 script URL。預設使用 Plausible outbound-link 與 file-download tracking script。 |

## 可以衡量什麼

- 文件站 page views，
- 文件站 outbound clicks，
- 文件站 file download events，
- 從 README CTA 進入 `/go/readme/.../` 的 click-through，
- GitHub 自身提供的 Release asset download counts。

## 不能衡量什麼

GitHub README views 不能載入專案自己的 analytics script。因此 README 的主要 CTA 會先經過透明的 `/go/readme/.../` landing pages。這些頁面可以衡量 click-through intent，然後轉向 GitHub 或 release asset。

專案不使用短網址服務；每個 redirect page 都保留手動 fallback link。

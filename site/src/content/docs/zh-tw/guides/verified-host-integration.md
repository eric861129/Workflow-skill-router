---
title: 建立 Verified Host adapter
description: 將 Host 擁有的權威能力接到 Router，同時不讓模型取得可執行或機密輸入。
---

這套 Integration Kit 提供 vendor-neutral 的 Host 開發契約。內附 adapter
標示為 `reference-not-production-authority`：它是 **not production**
authority，不是真實 Host pilot，也不能證明 `hybrid-full`。

## 權威資料只能由伺服器提供

Host 應先建立可信資源，再把 adapter 傳給 `composition.open`。模型或 MCP
參數不可指定 executable path、database、artifact location、environment
variable、secret 或 receipt authority。

## 實作 manifest

每個邊界都要宣告 owner、trusted input 或 receipt、freshness 規則、fail
closed 行為，以及 public-safe diagnostic：

- runtime authority 與 runtime context；
- scheduler 與 native Goal resume refresh；
- capability snapshot 與 policy snapshot；
- route validation、activation preflight 與 receipt verification；
- 具備 CAS、idempotency 的 append-only event coordination；
- evidence context、gate evaluation 與 gate persistence；
- artifact protection；
- evaluation authorization。

權威資料缺少、過期、偽造或綁定錯誤 session 時，必須在 mutation 前 fail
closed。公開輸出只能提供安全原因碼，不能洩漏可信值。

## 驗證開發 conformance

在 repository checkout 根目錄執行：

```powershell
$env:PYTHONPATH = (Resolve-Path 'packages/router-core/src').Path
python examples/reference-host-adapter/reference_host.py
```

通過報告涵蓋 composition、stale snapshot、forged receipt、wrong session、
CAS conflict、idempotent replay、native Goal resume refresh，以及 artifact
protection failure。之後再將記憶體內 ports 換成 Host-owned implementations，
並在 CI 執行同一套測試。

Runner 只會探測送入 `composition.open` 的 same `RouterCompositionPorts`；
probe inputs 不能用 shadow ports 取代它們。Manifest 的 authority flag 只是
declared metadata，因此 development conformance 一律回報
`production_authority_verified=false`。

Artifact conformance 會呼叫 `ArtifactStorePort.put_bytes`，與 `RouterService`
使用的正式 contract 相同。Restricted write 必須回傳綁定 digest 的 protected
reference，不可包含 path、location 或 URL。不安全輸出會回報
`artifact-reference-invalid`；儲存拒絕則安全化為 `artifact-protection-failed`。

Conformance 是工程 gate，不是 deployment attestation。宣稱 production-ready
或 `hybrid-full` 前，仍須另外完成真實 Host pilot。

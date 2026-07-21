---
title: 真實模型評測邊界
---

# 評測證據

Workflow Skill Router 將「確定性合約測試」、「真實模型行為評測」與
「真實 Host Pilot」分開處理。通過其中一種驗證，不代表其他層級也已完成。

## beta.5 Pilot 目前狀態

目前狀態是 `protocol-frozen-awaiting-real-pilot`：Pilot 規則已凍結，但尚未執行或計入任何真實 Pilot 任務。

- 對外發布的 V2 仍是 beta.3。
- beta.4 是已準備但尚未發布的原始碼版本。
- beta.5 是尚未發布、仍等待真實 Pilot 的原始碼工作。
- 協定、範本與 dry-run 都不是 Pilot 結果，也不會自動授權模型額度、Host
  存取或版本發布。

## 本機工作迴圈 Pilot

本機 Pilot 至少需要 20 個不同的真實任務：6 個 Single、8 個 Phased、6 個
Goal-like，其中至少 8 個使用 Personal 或 Workspace Profile。第一個任務開始前，
必須凍結下列資訊：

- source revision；
- runtime／package digest；
- protocol digest；
- reviewer；
- timestamp。

任務開始後產生的紀錄，不得暗中修改評分方式或門檻。正式門檻為：

- 人工修正工作模式的比例不得超過 10%；
- 未明確指定 Skill 的工作中，多餘 consent 詢問比例不得超過 5%；
- 使用者明確指定 Skill 並啟用 Explicit Skill Lock 時，不得使用未經同意的
  supporting Skill；
- Router-owned 本機工作恢復成功率至少 95%。

### 執行前的受限制綁定 manifest

Task 1 開始前，必須建立並由獨立 reviewer 審查 restricted binding manifest，其中
正好包含 20 筆 slot binding，順序固定為 `single-01..06`、`phased-01..08`、
`goal-01..06`。每次 run 使用獨立的 HMAC-SHA-256 secret，並依
`wsr-beta5-pilot-hmac-v1` 承諾 task identity、source identity、Profile
identity／revision、metric population flags 與 record integrity。受限制 manifest
內的 task／source identity 必須是 reviewer 指派的不透明 ID，不得放入 objective、
prompt 或路徑。32-byte secret、原始任務、來源路徑及完整 manifest 都不得公開。

HMAC 輸入是逐 byte 定義：先放 UTF-8
`workflow-skill-router/beta5-pilot/v1`、NUL、UTF-8 domain label、NUL，再將每個
欄位編成 `ASCII(decimal byte_length) + 0x3A + UTF-8 field bytes`。不得隱式套用
JSON serialization、Unicode normalization 或 locale-dependent conversion。

公開證據只保留不可逆的 binding-manifest commitment、task-set commitment 與
reviewer-attestation commitment。Reviewer 必須在 Task 1 前使用 restricted secret
確認任務真實性、20 個 task commitment 皆不同、source commitment 存在、slot ID
完整、Profile revision 正確，且 manifest digest 與 frozen run metadata 相符。這些
commitment 可支援後續 audit，但不能取代 reviewer 對「真實任務」的人工判斷。

Task 1 前必須執行 verifier：

```powershell
python evaluation/v2/pilots/verify_restricted_manifest.py `
  --manifest <restricted-manifest.json> `
  --secret-file <restricted-32-byte-secret.bin>
```

Verifier 只輸出 `valid` 與安全的診斷 `code`，不會輸出 secret 或私人 identity；
只有 `pilot-binding-valid` 可以繼續。

任何遺漏、歧義、重複、digest 不符或 Task 1 後遭修改的 binding／record，都會讓
整次 run 成為 `invalid`，不能降級成 `ineligible`。

### 非空的評分母體

四個 population flag 必須在執行前逐 slot 凍結：全部 20 筆都屬於
`manual_envelope`；`no_explicit_skill` 恰好是 `single-01..06` 與
`goal-01..04`；`explicit_lock` 恰好是 `phased-01..04`；
`router_local_resume` 恰好是 `phased-01..08` 與 `goal-05..06`。
`no_explicit_skill` 與 `explicit_lock` 不得重疊，只有八個 Phased slot 是
Profile-backed。

每個 eligible slot 都必須有 final record，每個 resume-eligible slot 都必須實際
attempt。人工修正率以 20 筆為分母；多餘 consent 率以凍結的 no-explicit-Skill
slots 為分母；Explicit Lock 計算所有未授權 support events；resume 成功率以所有
已 attempt 的 resume-eligible slots 為分母。缺少紀錄、分母為零或低於最低數量時，
gate 不成立且整次 run 無效，絕不允許 `0/0` 通過。

## 公開證據與隱私

公開產物只允許經過清理的彙總數據與不洩漏內容的 case-safe diagnostics。
下列資料必須留在受限制且經人工審查的證據區：

- 任務 objective 與原始 prompt；
- Repository／Workspace 路徑；
- instruction body 與 Profile 內容；
- secret、raw transcript；
- expected／actual Skill 值；
- 尚未審查的 evidence。

Raw result 與 checkpoint 只能寫入已驗證的 `restricted/` 目錄。Windows 必須使用
停止繼承、只允許目前使用者與 SYSTEM 的 DACL；POSIX 目錄與檔案權限必須分別
驗證為 `0700`、`0600`。未受保護的 transcript 不得 resume。

## Host 證據分成三條路徑

1. **離線參考適配器**：只證明開發階段的 conformance contract 可重現，不能算成
   真實 Host Pilot。
2. **真實 Host Pilot**：必須真的取得 Host-side authority、receipts，並完成獨立
   人工審查，才有資格建立 verified Host 證據。
3. **能力不可用**：若真實 Host API 不存在或沒有授權，應建立經審查的
   `capability-unavailable` attestation，誠實記錄缺少的能力與權限邊界。

離線參考適配器、能力不可用證據與準備文件都不能宣稱 `hybrid-full` 或 production
authority。

`skill-only-fallback` 與 `hybrid-full` 都不能自行宣告 reviewer authority。

## 為什麼現在不加入語意推薦器

目前決策是 `deterministic-default-no-semantic-recommender`。先使用可預測、可解釋的
Profile、alias、lint 與 `profile preview --explain`，不讓語意候選直接改寫持久化路由。

只有真實 Pilot 同時證明下列三點後，才可以提出實驗性語意推薦器提案：

1. 至少 10% 的合格人工修正確實來自 lexical synonym miss；
2. `profile preview --explain` 已排除 Profile 設定錯誤等確定性原因；
3. 已存在由 server 設定、只提供 advisory candidate 的 adapter，而且不能直接啟用
   Skill、改寫路由或授予權限。

沒有 Pilot 資料代表 gate 尚未滿足，不代表已證明語意推薦器表現不好。

## 真實模型評測邊界

Tier 0 Contract 只驗證確定性相容性。Behavior 與 Outcome 評測必須使用新的隔離
attempt、sealed scoring、paired manifest，且 hard violation 為零。沒有 adapter 時
狀態是 `manual-required`；沒有可信任的人工 attestation 時，輸出是
`review-required`，不得呈現為已審核分數。

Contract `workflow-skill-router.behavior-routing@2.3.0` 維持完整套件 13 個案例、beta
smoke 6 個案例。Smoke 保留一個雙回合 scoped-consent 案例，因此未來另行授權的
評測仍是 36 attempts、42 model turns。歷史 2.2.0 報表保留原始 case 與 instruction
digest，不會套用新版規則重算。

Deterministic reference-driver 只驗證 protocol 與 scoring pipeline，無法證明真實模型的行為。
只有取得明確模型額度授權、完成 fresh model execution、人工審查與
attestation 後，才能建立新的模型行為證據。

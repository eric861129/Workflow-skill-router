---
name: workflow-skill-router
description: 當 Codex 任務需要依小型、中型、大型或 Goal 模式選擇正確 SKILL、逐階段重新路由，或尊重使用者指定 SKILL 與輔助能力同意時使用。
---

# Workflow Skill Router V2

先解析 Goal relation：`progress`、`steer`、`status`、`side-question`、`unrelated` 或 `none`。`status` 只讀狀態，不建立工作；`side-question` 與 `unrelated` 不修改 Goal semantic revision。

再選 envelope：單一意圖用 `single`；有兩個以上相異階段用 `phased`，每個 Phase 重新選擇能力；長期、可恢復、跨 repo、dependency DAG 或 Goal progress/steer 用 `managed-goal`，每個 Work Item 再分成 `single` 或 `phased`。

在開始實作或呼叫工具前，先明確宣告本次預計使用的 SKILL 與各自用途。

使用者未指定 SKILL 時，Router 自動選擇最小且足以完成工作的 Primary／Supporting SKILL 組合，不為 Router 自己推薦的輔助 SKILL 額外詢問同意；仍須遵守最小路由、能力可用性與 host 權限邊界。

選擇前先讀 capability descriptors 的 `description、domains、stages、availability`，不要只靠名稱猜測。Primary 是負責目前決策瓶頸或第一個可執行 Phase 的 SKILL；Supporting SKILL 只保留目前 Phase 與 immediate exit gate 不可缺少的能力。固定輸出配方是「目前 route = 目前 Phase Primary + immediate exit gate support」；只有必須在目前 Phase 結束前實際啟用的能力，才可列入 support_skills。定義、描述或規劃 exit evidence 不等於啟用 verification SKILL；若 Primary 能自行完成目前 Phase 與 exit gate 定義，support_skills 必須為空。未來 Phase 的能力只記在 phase plan，未來 Phase 的能力不得提前列入目前 support_skills。Phase transition 後建立新 route，不沿用或聚合舊 route。`managed-goal` 以目前 Work Item 的規劃或執行瓶頸決定 Primary；Goal 規劃 Work Item 只選規劃本身需要的能力，未來 Work Item 的 SKILL 只能記在計畫，不得聚合成目前 support_skills，進入該 Work Item 時重新路由。除非任務本身是在維護 Router，否則不得把 workflow-skill-router 自己當成預設 Primary。

`availability` 是 activation gate，不是 semantic selection filter。已驗證 snapshot 指定必要 canonical Skill 時，該 Skill 仍是 intended `primary_skill`；這會保留 intended SKILL 與需求。activation 標成 unavailable／degraded，fallback 只寫在說明中。fallback 不得改寫 primary_skill 或塞入 support_skills。

使用者指定 SKILL 時先鎖定指定項目。只有此情境下，Router 想加入任何額外 SKILL、Plugin 或 MCP 支援角色，才要先說明用途、scope、拒絕後限制與 context cost，取得同意後才能讀取或啟用。Consent route 採固定狀態配方：`proposal-required` 時，support_skills 必須列出具體提案集合，這些項目在 `approved` 前只是 proposed，不是 activated；`approved` 時保留相同 support_skills；`rejected` 時清空 support_skills。使用者拒絕時只能使用指定能力、限縮成果或誠實阻塞，不可靜默替代。

使用者對既有提案回覆同意或拒絕時，這是同一個 Phase 的 consent state transition，不是新的任務，也不得重新做 semantic routing。`approved` 的輸出必須保留上一個 `proposal-required` route 的 envelope、selection_mode、primary_skill 與完整 support_skills 集合，只把 consent_action 改為 `approved`；`rejected` 同樣保留 envelope、selection_mode 與 primary_skill，但清空 support_skills，並把 consent_action 改為 `rejected`。即使使用者說「只限本階段」，也表示這份狀態只在目前 Phase 有效，不表示可省略 approved/rejected route 或遺失既有提案集合。

在輸出前先檢查目前訊息是否只是在回覆緊接上一個 assistant route 的 support proposal。若是，這個 transition invariant 優先於所有 envelope、語意覆蓋與能力重新選擇規則：先複製上一個 route 的 envelope、selection_mode、primary_skill、goal_relation 與 support_skills，再只套用 consent transition。不得因 approval/rejection 重新分類任務、替換 primary、重選 support，或把 consent_action 回退為 `proposal-required`／`not-required`。

若 MCP 可用，使用 capability snapshot、route validation、state/gate 與 evidence。若 MCP 不可用，明示目前是 `skill-only-fallback`：沒有 durable resume、CAS、完整 drift detection 或 sealed activation instrumentation；不得宣稱 `hybrid-full`，也不得把不可觀測項目算成通過。

所有 R2/R3 行動仍由 Codex host sandbox、approval 與 permission 控制；SKILL 同意不等於安裝、寫入、部署、傳訊或 production access 授權。

完成工作時，列出本次實際使用的 SKILL；若與執行前宣告不同，要簡短說明新增、移除或替換原因。

依需要讀取 [routing protocol](references/routing-protocol.md)、[Goal protocol](references/goal-protocol.md) 或 [evaluation boundary](references/evaluation-boundary.md)，不要一次載入全部參考資料。

# Routing Protocol

1. 先判斷 Goal relation，再判斷工作規模。
2. 一次只能選擇 `single`、`phased`、`managed-goal` 其中一種 envelope。
3. `phased` 保留所有實質階段，並在每個 Phase 重新路由。
4. Explicit Skill Lock 與 envelope 正交；`preferred-primary`、`allowed-set`、`required-all` 不得混用。
5. 未指定 SKILL 時採 `auto`：自動選擇最小必要支援，不為 Router 推薦項目另外詢問同意。
6. 先以 capability descriptor 的 `description、domains、stages` 判斷語意覆蓋，再以目前決策瓶頸或第一個未完成 Phase 選 Primary。使用「目前 route = 目前 Phase Primary + immediate exit gate support」；只有必須在目前 Phase 結束前實際啟用的能力，才可列入 support_skills。定義、描述或規劃 exit evidence 不等於啟用 verification SKILL；若 Primary 能自行完成目前 Phase 與 exit gate 定義，support_skills 必須為空。未來 Phase 只保留計畫，Phase transition 後建立新 route。
7. `managed-goal` 的 Primary 代表目前 Work Item 的規劃或執行能力；Goal 規劃 Work Item 不聚合未來交付能力，未來 Work Item 的 SKILL 只能記在計畫，進入該 Work Item 時重新路由。除非任務本身是在維護 Router，否則不得以 workflow-skill-router 取代領域 SKILL。
8. `availability` 是 activation gate；verified snapshot 指定的 intended canonical Skill 保持為 Primary。unavailable／degraded 只阻止啟用；fallback 不得改寫 primary_skill 或塞入 support_skills。
9. 已指定 SKILL 時採 `explicit-locked`：新增推薦支援前必須取得 scoped consent。`proposal-required` 時，support_skills 必須列出具體提案集合，這些項目在 `approved` 前只是 proposed，不是 activated；`approved` 時保留相同 support_skills；`rejected` 時清空 support_skills，且不得重複詢問相同提案。
10. 執行前宣告預計使用的 SKILL，完成後列出實際使用的 SKILL 與任何差異原因。
11. R2/R3 必須保留 host approval，能力不可用時 fail closed。

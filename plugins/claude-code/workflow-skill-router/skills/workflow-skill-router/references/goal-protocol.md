# Goal Protocol

- `status` 是唯讀查詢，不建立 Work Item。
- `progress` 與 `steer` 進入 managed Goal；`side-question` 與 `unrelated` 不改 Goal semantic revision。
- 每個 Work Item 維持 dependency、read/write scope、entry/exit gate 與 evidence requirements。
- 每個 Work Item 再判斷 `single` 或 `phased`，resume 前刷新 Goal、workspace、capabilities 與 evidence。
- Goal 規劃 Work Item 的 route 只包含規劃 Primary 與規劃 exit gate 必要 support；未來交付能力留在 Work Graph。
- 未來 Work Item 的 SKILL 只能記在計畫，不得聚合成目前 `support_skills`；進入該 Work Item 時重新路由。
- Native Goal 只產生 `GoalStatusCandidate`；Router 不直接修改 host Goal 狀態。
- blocked 只在同一阻塞條件連續三個可計數 Goal turn 且沒有可執行必要工作時成立。

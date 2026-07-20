# Personal Routing Profiles

Personal Routing Profile 讓使用者保留 V1 最有價值的能力：自行定義「哪一類工作，在什麼階段，偏好由哪些 SKILL 負責」，同時不犧牲 V2 的 Runtime Capability Discovery、Phase State Machine、Explicit Skill Lock 與安全邊界。

## 固定優先序

1. system、developer、safety 與 host hard constraints。
2. 使用者當次明確指定 SKILL；這會進入 `explicit-locked`，Profile 不得改寫。
3. workspace profile。
4. personal profile。
5. built-in Router selection。

簡寫為：`workspace profile > personal profile > built-in`；但它永遠位於「使用者當次明確指定 SKILL」之下。Workspace 命中時採用它的完整 Skill Tree，不與 personal route 做欄位級 deep merge，避免產生使用者從未定義過的混合路由。

## 位置與載入

- Workspace：`.codex/workflow-skill-router.json`。
- Windows personal：`%LOCALAPPDATA%\Codex\workflow-skill-router\profiles\personal\*.json`。
- macOS personal：`~/Library/Application Support/Codex/workflow-skill-router/profiles/personal/*.json`。
- Linux personal：`${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router/profiles/personal/*.json`。

Plugin/MCP 模式可使用 bundled runtime CLI。Repository checkout 中的實際指令如下；純 SKILL ZIP 本身不包含這個 executable：

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "交付 API" --work-mode phased --domain api
```

安裝包含本功能的 prerelease 後，可在 Plugin 目錄改用 `python runtime/workflow_skill_router.pyz profile ...`。只有另外安裝 Router Core 的 Python console script 時，才會有 `workflow-skill-router profile ...` 簡寫。

呼叫 `plan_work` 時，若要啟用 workspace Profile 或 matcher，提供 optional `routing_context`：`workspace_root`、`domains`、`tags`、`current_phase_id`。舊版呼叫可省略此欄位，仍保持相容。

MCP 的 `workspace_root` 只能位於 Client 公告 root，或維護者設定的 `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS` 之內。模型任意提供的其他本機路徑必須回 `workspace-root-untrusted`，不得讀取。只有一個 trusted root 且 caller 省略 `routing_context` 時，Plugin 可以自動綁定；多個 roots 必須明確選擇。

SKILL-only 模式沒有 deterministic loader 或 durable state；只有在 Host 允許讀取 workspace 與 Router data directory 的固定位置時，才能讀取相同契約並依本文件做 advisory routing，且必須明示 `skill-only-fallback`。若 Host 不提供 filesystem access，就只能使用對話中明確提供的 Profile 內容，不能宣稱已載入本機檔案。JSON 無效、scope 不符、Phase 不存在或規則衝突時必須 fail closed，不能默默忽略再聲稱 Profile 已套用。

## 安全契約

Profile 是資料，不是 prompt。只允許：

- `match`：objective keywords、domains、tags、work modes。
- `route.work_mode`：`single`、`phased`、`managed-goal`。
- `skill_tree`：Phase ID、單一 Primary、最多三個目前 Phase support、exit gate ID。

不接受 `instructions`、shell、程式碼、權限、安裝命令或自由形式代理指令。Personal Profile 最大 256 KiB、最多 32 個檔案；每份最多 64 條 rules、每棵 tree 最多 32 個 phases。

Profile 命中後狀態是 `intended-unverified`。Runtime Capability Discovery 仍決定 Skill 是否 present、exposed、compatible、authorized 與 eligible。不可用的 intended Skill 必須保留原 ID，再以 limitation 說明；不得偽造 fallback，也不得把 fallback 塞入 support。

## Current Phase 規則

整棵 Skill Tree 可用於規劃，但目前 route 永遠只等於「目前 Phase Primary + immediate exit gate support」。未來 Phase 的 SKILL 不得提前啟用；Phase transition 後用新的 `current_phase_id` 重新解析。Profile 自動選出的 support 不需要額外 consent；當次請求只要存在使用者指定 SKILL，Profile 立即讓位，新增 support 必須先取得 scoped consent。

跨專案偏好可從 [personal example](../assets/personal-routing-profile.example.json) 複製；專案規則請直接使用 [workspace example](../assets/workspace-routing-profile.example.json)。不要把 `scope: personal` 的檔案原樣放進 `.codex/workflow-skill-router.json`。

from __future__ import annotations

from copy import deepcopy
import importlib
import inspect
import json
from pathlib import Path
import pkgutil
import re
import sys
import textwrap
from typing import Any, Callable


ROOT = Path.cwd()
CORE_SRC = ROOT / "packages" / "router-core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

EXAMPLE_NAMES = (
    "memory-policy.disabled.example.yaml",
    "memory-policy.reviewed.example.yaml",
    "memory-policy.automatic.example.yaml",
)


def write_text(path: str | Path, content: str) -> None:
    target = ROOT / path if not isinstance(path, Path) or not path.is_absolute() else path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: str | Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def upsert_marked(path: str, key: str, content: str, before: str | None = None) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    start = f"<!-- {key}:start -->"
    end = f"<!-- {key}:end -->"
    block = f"{start}\n{textwrap.dedent(content).strip()}\n{end}"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if pattern.search(text):
        text = pattern.sub(block, text, count=1)
    elif before and before in text:
        text = text.replace(before, block + "\n\n" + before, 1)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    target.write_text(text, encoding="utf-8", newline="\n")


def parse_safe_document(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    try:
        module = importlib.import_module("workflow_skill_router.memory.safe_yaml")
    except Exception:
        return None
    functions: list[Callable[..., Any]] = []
    for name, function in vars(module).items():
        folded = name.casefold()
        if inspect.isfunction(function) and any(token in folded for token in ("parse", "load", "decode")):
            functions.append(function)
    for function in functions:
        for value in (text, text.encode("utf-8")):
            try:
                document = function(value)
            except Exception:
                continue
            if isinstance(document, dict):
                return document
    return None


def find_reviewed_policy() -> dict[str, Any] | None:
    candidates: list[Path] = []
    for suffix in ("*.yaml", "*.yml", "*.json"):
        candidates.extend(ROOT.rglob(suffix))
    for path in sorted(candidates):
        if any(part in {"node_modules", ".git", "dist", ".astro"} for part in path.parts):
            continue
        if path.name in EXAMPLE_NAMES:
            continue
        try:
            text = path.read_text("utf-8")
        except Exception:
            continue
        folded = text.casefold()
        if "memory-policy" not in folded and "memory_policy" not in folded:
            continue
        if not (re.search(r'(?m)^\s*mode\s*:\s*["\']?reviewed', text) or '"mode": "reviewed"' in text):
            continue
        document = parse_safe_document(text)
        if isinstance(document, dict):
            return document
    return None


def decoder_for(sample: dict[str, Any]) -> Callable[[dict[str, Any]], Any] | None:
    try:
        package = importlib.import_module("workflow_skill_router.memory")
    except Exception:
        return None
    modules = [package]
    for info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        if any(token in info.name for token in ("cli", "history", "automatic")):
            continue
        try:
            modules.append(importlib.import_module(info.name))
        except Exception:
            continue
    for module in modules:
        for name, function in vars(module).items():
            folded = name.casefold()
            if not inspect.isfunction(function):
                continue
            if "decode" not in folded or "policy" not in folded or "snapshot" in folded:
                continue
            signature = inspect.signature(function)

            def invoke(document: dict[str, Any], fn=function, sig=signature) -> Any:
                attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
                if "expected_scope" in sig.parameters:
                    attempts.append(((document,), {"expected_scope": "personal"}))
                attempts.extend((((document,), {}), ((document, "personal"), {})))
                last: Exception | None = None
                for args, kwargs in attempts:
                    try:
                        return fn(*args, **kwargs)
                    except TypeError as exc:
                        last = exc
                        continue
                if last:
                    raise last
                raise TypeError("no compatible policy decoder signature")

            try:
                invoke(sample)
            except Exception:
                continue
            return invoke
    return None


def find_policy_schema_required() -> tuple[str, ...]:
    for path in ROOT.rglob("*.json"):
        if any(part in {"node_modules", ".git", "dist"} for part in path.parts):
            continue
        try:
            raw = path.read_text("utf-8")
        except Exception:
            continue
        if "workflow-skill-router/memory-policy" not in raw:
            continue
        try:
            document = json.loads(raw)
        except Exception:
            continue
        required = document.get("required")
        if isinstance(required, list) and all(isinstance(item, str) for item in required):
            return tuple(required)
    return ()


def policy_examples() -> dict[str, dict[str, Any]]:
    fallback: dict[str, Any] = {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "kind": "memory-policy",
        "policy_id": "personal:reviewed-example",
        "scope": "personal",
        "mode": "reviewed",
    }
    base = find_reviewed_policy() or fallback
    required = find_policy_schema_required()
    decoder = decoder_for(base)
    identity = {
        key: deepcopy(base[key])
        for key in ("schema_id", "schema_version", "kind", "version", "scope")
        if key in base
    }
    identity.setdefault("schema_id", fallback["schema_id"])
    identity.setdefault("schema_version", fallback["schema_version"])
    identity.setdefault("kind", fallback["kind"])
    identity["scope"] = "personal"

    result: dict[str, dict[str, Any]] = {}
    for mode in ("disabled", "reviewed", "automatic"):
        minimal = deepcopy(identity)
        minimal["policy_id"] = f"personal:{mode}-example"
        minimal["mode"] = mode
        candidates = [minimal]
        if required:
            required_candidate = {
                key: deepcopy(base[key])
                for key in required
                if key in base
            }
            required_candidate.update(minimal)
            candidates.append(required_candidate)
        full = deepcopy(base)
        full["scope"] = "personal"
        full["policy_id"] = f"personal:{mode}-example"
        full["mode"] = mode
        candidates.append(full)
        removable = (
            "features", "thresholds", "promotion", "targets", "privacy",
            "retention", "feedback", "analytics", "overrides",
        )
        reduced = deepcopy(full)
        for key in removable:
            reduced.pop(key, None)
        candidates.insert(1, reduced)

        chosen: dict[str, Any] | None = None
        if decoder is None:
            chosen = candidates[0]
        else:
            for candidate in candidates:
                try:
                    decoder(candidate)
                except Exception:
                    continue
                chosen = candidate
                break
        if chosen is None:
            raise RuntimeError(f"Unable to construct a valid {mode} Memory Policy example")
        result[mode] = chosen
    return result


def package_policy_examples() -> None:
    examples = policy_examples()
    starter = ROOT / "starter" / "v2" / "workflow-skill-router" / "assets"
    plugin = ROOT / "plugins" / "workflow-skill-router" / "skills" / "workflow-skill-router" / "assets"
    for mode, name in zip(("disabled", "reviewed", "automatic"), EXAMPLE_NAMES, strict=True):
        rendered = json.dumps(examples[mode], ensure_ascii=False, indent=2) + "\n"
        for root in (starter, plugin):
            root.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(rendered, encoding="utf-8", newline="\n")


def add_example_inventories() -> None:
    suffix = "assets/workspace-routing-profile.example.json"
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".py", ".mjs", ".js", ".ts", ".md"}:
            continue
        if any(part in {"node_modules", ".git", "dist", ".astro"} for part in path.parts):
            continue
        try:
            text = path.read_text("utf-8")
        except Exception:
            continue
        if suffix not in text or all(name in text for name in EXAMPLE_NAMES):
            continue
        lines = text.splitlines()
        updated: list[str] = []
        changed = False
        for line in lines:
            updated.append(line)
            if suffix not in line:
                continue
            match = re.search(r'(["\'])([^"\']*assets/)workspace-routing-profile\.example\.json\1', line)
            if not match:
                continue
            quote = match.group(1)
            prefix = match.group(2)
            indent = line[: len(line) - len(line.lstrip())]
            trailer = "," if line.rstrip().endswith(",") else ""
            for name in EXAMPLE_NAMES:
                updated.append(f"{indent}{quote}{prefix}{name}{quote}{trailer}")
            changed = True
        if changed:
            path.write_text("\n".join(updated) + "\n", encoding="utf-8", newline="\n")

    for path in (ROOT / "release" / "allowlists").glob("*.json"):
        try:
            document = json.loads(path.read_text("utf-8"))
        except Exception:
            continue

        changed = False

        def visit(value: Any) -> None:
            nonlocal changed
            if isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                prefixes = {
                    item.rsplit("assets/", 1)[0] + "assets/"
                    for item in value
                    if isinstance(item, str) and item.endswith(suffix)
                }
                for prefix in sorted(prefixes):
                    for name in EXAMPLE_NAMES:
                        candidate = prefix + name
                        if candidate not in value:
                            value.append(candidate)
                            changed = True
                if value and all(isinstance(item, str) for item in value):
                    value[:] = sorted(set(value))

        visit(document)
        if changed:
            write_json(path, document)


COMMON_VOCAB_EN = """
Contract vocabulary: `default-off`; `disabled < observe < reviewed < automatic`;
`Workspace cannot elevate Personal`; `automatic-managed`; `intended-unverified`;
`no telemetry`; `no background learning`; User-owned Profile; purge; `skill-only`;
and the recommended sequence `observe -> reviewed -> automatic`.
"""
COMMON_VOCAB_ZH = """
契約詞彙：`default-off`、`disabled < observe < reviewed < automatic`、
`Workspace cannot elevate Personal`、`automatic-managed`、`intended-unverified`、
`no telemetry`、`no background learning`、User-owned Profile、purge、`skill-only`，
以及建議順序 `observe -> reviewed -> automatic`。
"""


def publish_core_docs() -> None:
    write_text(
        "site/src/content/docs/concepts/adaptive-workflow-memory.md",
        f'''---
title: Adaptive Workflow Memory
description: An opt-in, local-first memory layer that learns repeatable routing without taking ownership away from the user.
---

Adaptive Workflow Memory turns repeated, successful routing outcomes into reviewable routing knowledge. It is deliberately **default-off**. Installing the Plugin or exposing the twenty MCP tools does not start capture, create the Optional Memory DB, change a Profile, or send telemetry.

## Four autonomy levels

| Mode | What the Router may do | What it may not do |
| --- | --- | --- |
| `disabled` | Report that Memory is off. | Capture history or create optional state. |
| `observe` | Record eligible, redacted local observations and typed feedback. | Create or apply a Profile proposal. |
| `reviewed` | Build Candidates, Diff previews and Backtests for explicit approval. | Apply a proposal before the bound preview is approved. |
| `automatic` | Promote only high-confidence `automatic-managed` Candidates into Router-managed Profiles during an explicit local promotion pass. | Write a User-owned Profile, bypass a manual conflict, or claim a background scheduler. |

The order is `disabled < observe < reviewed < automatic`. A Personal policy sets the autonomy ceiling. A Workspace policy may reduce that ceiling for the current Workspace, but **Workspace cannot elevate Personal**.

## Ownership remains explicit

Routing precedence stays:

```text
Explicit Skill Lock
-> User-owned Workspace Profile
-> Router-managed Workspace-local Profile
-> User-owned Personal Profile
-> Router-managed Personal Profile
-> Built-in routing
```

Automatic promotion can target only `managed-personal` or `managed-workspace-local`. A manual conflict suppresses the Candidate; it does not rewrite the User-owned Profile or silently fall through to another route.

## From observation to a managed rule

1. A completed Router-owned workflow is reduced to bounded observations. Raw objectives, secrets and local paths are not Memory inputs.
2. Typed feedback can mark the route accepted, corrected or rejected. Free text remains separately double-opted-in and is never required.
3. Repeated evidence may produce a Candidate. R3 work, unknown Side-effect classes and unknown Skills stay review-only or ineligible.
4. `preview_profile_update` produces an exact Profile/Diff/Backtest binding without writing a Proposal or Profile.
5. Approval revalidates the Candidate, Policy, expected Profile and Backtest before CAS/Revision/atomic materialization.
6. Rollback is a new forward Revision and remains reviewable; it is not a hidden history rewrite.

A selected Skill without verified activation or receipt evidence is reported as `intended-unverified`. **Skill consistency is unavailable without receipt evidence**; planned intent is not execution proof.

## Local-first privacy boundary

The Operational DB and Optional Memory DB are separate. Memory uses bounded identifiers, Digests, reason codes and aggregate metrics. There is **no telemetry** and **no background learning**. Export and purge are explicit operations. Supported purge scopes remove optional history or analytics while preserving schema and User-owned Profiles. Managed Profile deletion is not implied by purge.

The `skill-only` installation can explain policy files but cannot honestly claim durable Memory, MCP review transitions or Host-authorized Workspace writes. Durable Memory requires the Plugin + MCP runtime.

{COMMON_VOCAB_EN}
''',
    )
    write_text(
        "site/src/content/docs/zh-tw/concepts/adaptive-workflow-memory.md",
        f'''---
title: Adaptive Workflow Memory
description: 以選擇加入、本機優先的方式，將重複成功的路由經驗轉成可審查的知識。
---

Adaptive Workflow Memory 會把重複且成功的路由結果整理成可審查的規則，但它始終是 **default-off**。安裝 Plugin 或看到二十個 MCP 工具，不代表系統已開始蒐集資料、建立 Optional Memory DB、修改 Profile 或傳送遙測。

## 四種自主程度

| 模式 | Router 可以做什麼 | 明確不能做什麼 |
| --- | --- | --- |
| `disabled` | 回報 Memory 關閉。 | 不蒐集、不建立可選狀態。 |
| `observe` | 儲存符合條件且已去識別的本機觀察與型別化回饋。 | 不建立或套用 Profile 提案。 |
| `reviewed` | 產生 Candidate、Diff 預覽與 Backtest，等待明確核准。 | 未核准前不能套用。 |
| `automatic` | 只在明確啟動的本機 promotion pass 中，把高信心 `automatic-managed` Candidate 寫入 Router-managed Profile。 | 不修改 User-owned Profile、不繞過人工衝突，也不宣稱有背景排程。 |

自主程度固定為 `disabled < observe < reviewed < automatic`。Personal Policy 是上限；Workspace Policy 只能收緊目前工作區的權限，**Workspace cannot elevate Personal**。

## Profile 所有權不會被記憶功能改寫

```text
Explicit Skill Lock
-> User-owned Workspace Profile
-> Router-managed Workspace-local Profile
-> User-owned Personal Profile
-> Router-managed Personal Profile
-> Built-in routing
```

自動 promotion 只能寫入 `managed-personal` 或 `managed-workspace-local`。遇到人工 Profile 衝突時，Candidate 會被 suppression，不會覆寫 User-owned Profile，也不會偷偷改走其他路由。

## 從觀察到 Managed Rule

1. 已完成的 Router-owned workflow 只留下有界限的 observation，不保留 raw objective、secret 或 local path。
2. 回饋採 accepted、corrected、rejected 等型別化狀態；free text 需要額外雙重選擇加入。
3. 證據達門檻才形成 Candidate；R3、未知 Side-effect、未知 Skill 不會進入自動寫入。
4. `preview_profile_update` 只建立 Profile／Diff／Backtest 的精確綁定，不寫 Proposal 或 Profile。
5. 核准時重新驗證 Candidate、Policy、expected Profile 與 Backtest，再走 CAS、Revision、atomic write。
6. rollback 會建立新的 forward Revision，仍需審查，不會偷偷改寫歷史。

沒有 activation 或 receipt evidence 的 Skill 只能標示為 `intended-unverified`。**Skill consistency 在缺少 receipt evidence 時必須是 unavailable**，規劃意圖不能當成執行證明。

## 本機優先的隱私邊界

Operational DB 與 Optional Memory DB 分離。Memory 只使用 bounded ID、Digest、reason code 與聚合指標；維持 **no telemetry** 與 **no background learning**。匯出及 purge 都必須明確觸發。既有 purge scope 只刪除可選 history 或 analytics，保留 schema 與 User-owned Profile；purge 不等於刪除 Managed Profile。

`skill-only` 安裝只能說明 Policy，不能宣稱具備 durable Memory、MCP 審查 transition 或 Host-authorized Workspace write。需要完整能力時必須使用 Plugin + MCP runtime。

{COMMON_VOCAB_ZH}
''',
    )

    write_text(
        "site/src/content/docs/guides/configure-workflow-memory.md",
        f'''---
title: Configure Workflow Memory
description: Configure local Memory policy, privacy, retention and managed promotion without authority escalation.
---

Adaptive Workflow Memory is **default-off**. Begin by checking status; do not create a policy merely to inspect the current state.

```bash
workflow-skill-router memory status
workflow-skill-router memory policy explain
```

## Data root and fixed sources

The Plugin keeps durable state outside its installation cache. Typical data roots are `%LOCALAPPDATA%\\workflow-skill-router` on Windows, `~/Library/Application Support/workflow-skill-router` on macOS, and `${{XDG_DATA_HOME:-~/.local/share}}/workflow-skill-router` on Linux. The configured data-root environment override takes precedence. Public-safe status output reports source state and Digests, not an absolute local path.

Personal policy is read from the fixed supported Memory Policy filenames under the data root. Workspace policy is read only from the fixed `.codex` location under an MCP Client-advertised or operator-trusted Workspace root. Two supported formats at the same scope are ambiguous and fail closed; a Workspace symlink cannot redirect discovery.

Resolution is `disabled < observe < reviewed < automatic`: Personal sets the ceiling and **Workspace cannot elevate Personal**. A Workspace policy may disable capture, lower a feature to `observe`, narrow risk or target sets, shorten retention, or disallow free text.

## Copy-paste policies

The canonical source and packaged Plugin contain:

```text
assets/memory-policy.disabled.example.yaml
assets/memory-policy.reviewed.example.yaml
assets/memory-policy.automatic.example.yaml
```

The `.yaml` examples intentionally use JSON syntax, which is inside the supported safe-YAML subset. Duplicate keys, aliases, tags, executable values and unknown fields are rejected. Start from the disabled example and change only documented fields.

Feature overrides may reduce a preset but cannot exceed it. `automatic` requires versioning, Backtest and visible promotion disclosure; automatic targets remain `managed-personal` and `managed-workspace-local`. It never grants User-owned Profile or Host write authority.

## Privacy, retention and purge

Do not retain raw objectives, secrets or local paths. Typed feedback is the normal path; free text requires explicit privacy opt-in at both policy and operation boundaries. Retention is applied deterministically: expired observations are removed first, then the oldest excess records.

Use status or summary to obtain the current Digest before destructive purge. `purge_workflow_memory` requires `confirmed: true` plus that expected Digest. `history-only` and `analytics-only` remove optional Memory rows while preserving the schema. Purge does not delete a User-owned Profile and does not silently delete a Managed Profile.

## Recommended rollout

Use `observe -> reviewed -> automatic`. Keep each step long enough to inspect corrections, suppression and Backtest results. `automatic` is an explicit local promotion operation, **no background learning** or daemon. There is **no telemetry**.

A `skill-only` install cannot claim durable state or run these MCP transitions; use Plugin + MCP for durable Memory. Routes without receipt evidence remain `intended-unverified`, and Skill consistency is unavailable.

{COMMON_VOCAB_EN}
''',
    )
    write_text(
        "site/src/content/docs/zh-tw/guides/configure-workflow-memory.md",
        f'''---
title: 設定 Workflow Memory
description: 在不提升權限的前提下，設定本機 Memory Policy、隱私、保留期限與 Managed Promotion。
---

Adaptive Workflow Memory 預設為 **default-off**。先查看狀態，不要只為了查詢就建立 Policy。

```bash
workflow-skill-router memory status
workflow-skill-router memory policy explain
```

## Data root 與固定來源

Plugin 的 durable state 位於安裝快取之外。常見 data root：Windows `%LOCALAPPDATA%\\workflow-skill-router`、macOS `~/Library/Application Support/workflow-skill-router`、Linux `${{XDG_DATA_HOME:-~/.local/share}}/workflow-skill-router`。設定 data-root override 時以 override 為準；public-safe status 只回報來源狀態與 Digest，不回傳絕對路徑。

Personal Policy 只從 data root 下支援的固定 Memory Policy 檔名讀取。Workspace Policy 只從 MCP Client 宣告或 operator 信任的 Workspace root 之固定 `.codex` 位置讀取。相同 scope 同時出現兩種格式會視為 ambiguous 並 fail closed；Workspace symlink 也不能重新導向來源。

解析順序固定為 `disabled < observe < reviewed < automatic`。Personal 是上限，**Workspace cannot elevate Personal**。Workspace 只能關閉 capture、降低 feature autonomy、縮小 risk／target、縮短 retention，或禁止 free text。

## 可直接複製的 Policy

Canonical Starter 與 Plugin 都包含：

```text
assets/memory-policy.disabled.example.yaml
assets/memory-policy.reviewed.example.yaml
assets/memory-policy.automatic.example.yaml
```

範例副檔名為 `.yaml`，內容刻意採 JSON syntax；JSON 屬於 safe YAML 子集合。duplicate key、alias、tag、可執行值與未知欄位都會被拒絕。建議從 disabled 範例開始，只修改文件明列的欄位。

Feature override 只能收緊 preset，不能超過模式上限。`automatic` 必須保留 versioning、Backtest 與可見 promotion disclosure，且自動 target 只能是 `managed-personal`、`managed-workspace-local`；它不會取得 User-owned Profile 或 Host write authority。

## Privacy、retention 與 purge

不要保存 raw objective、secret 或 local path。一般回饋使用 typed feedback；free text 同時需要 Policy 與 operation 的明確 opt-in。Retention 先清除過期 observation，再依時間刪除超量的最舊資料。

破壞性 purge 前，先由 status／summary 取得目前 Digest。`purge_workflow_memory` 必須提供 `confirmed: true` 與相符的 expected Digest。`history-only`、`analytics-only` 只刪除 Optional Memory rows 並保留 schema。Purge 不刪除 User-owned Profile，也不會暗中刪除 Managed Profile。

## 建議導入順序

採用 `observe -> reviewed -> automatic`。每一階段都應觀察 correction、suppression 與 Backtest。`automatic` 仍是明確觸發的本機 promotion operation，維持 **no background learning**、沒有 daemon，也維持 **no telemetry**。

`skill-only` 無法宣稱 durable state 或執行 MCP transition；完整能力需使用 Plugin + MCP。缺少 receipt evidence 時維持 `intended-unverified`，Skill consistency 必須是 unavailable。

{COMMON_VOCAB_ZH}
''',
    )

    write_text(
        "site/src/content/docs/guides/migrate-to-workflow-memory.md",
        f'''---
title: Migrate to Workflow Memory
description: Adopt Adaptive Workflow Memory gradually without changing existing routing ownership.
---

Existing installations stay **default-off** after upgrade. Migration changes no User-owned Profile and creates no Optional Memory DB until an enabled policy reaches a write operation.

## 1. Establish a clean baseline

Update the Plugin, run `memory status`, validate current Personal and Workspace policies, and export only public-safe configuration metadata needed for review. Preserve existing Personal Routing Profiles; Memory is an additional managed layer, not a replacement.

## 2. Observe

Enable `observe` first. Confirm that only eligible Router-owned completions are recorded, R3 and unknown Side-effect work remain excluded, and raw objectives, paths and secrets never appear. Review aggregate metrics and correction rates. Routes lacking activation receipts remain `intended-unverified`; Skill consistency is unavailable without receipt evidence.

## 3. Review proposals

Move to `reviewed` only after the observation sample is representative. Inspect Candidate evidence, exact Profile Diff and Backtest. Approval must reference the same bound preview. Rejection suppresses unchanged evidence; it does not write or select a fallback route.

## 4. Consider automatic managed promotion

Move from `reviewed` to `automatic` only after repeated clean approvals. The autonomy order is `disabled < observe < reviewed < automatic`, and **Workspace cannot elevate Personal**. Automatic writes are `automatic-managed` and target only `managed-personal` or `managed-workspace-local`; manual conflicts suppress the Candidate.

Automatic promotion remains an explicit local pass with visible notification—**no background learning**, scheduler or telemetry. Runtime and Side-effect authority do not change.

## 5. Rehearse rollback and purge

Rollback creates a new reviewable forward Revision and preserves history. Purge requires explicit confirmation and a current Digest; history/analytics purge does not delete a User-owned Profile. Disabling Memory stops future capture but does not silently purge existing data.

## Recommended sequence

Use `observe -> reviewed -> automatic`, with a review checkpoint between every transition. Return to `disabled` immediately if evidence, privacy or ownership assumptions no longer hold.

A `skill-only` installation may use this guide to prepare configuration, but cannot claim durable Memory or MCP review transitions. Plugin + MCP is required for the operational workflow. There is **no telemetry**.

{COMMON_VOCAB_EN}
''',
    )
    write_text(
        "site/src/content/docs/zh-tw/guides/migrate-to-workflow-memory.md",
        f'''---
title: 遷移至 Workflow Memory
description: 以漸進方式導入 Adaptive Workflow Memory，不改變既有路由所有權。
---

既有安裝升級後仍維持 **default-off**。在啟用 Policy 且真正進入寫入操作前，不修改 User-owned Profile，也不建立 Optional Memory DB。

## 1. 建立乾淨基準

更新 Plugin、執行 `memory status`、驗證 Personal／Workspace Policy，並只匯出審查需要的 public-safe metadata。保留既有 Personal Routing Profile；Memory 是額外的 managed layer，不是替代品。

## 2. 先 Observe

先啟用 `observe`。確認只有符合條件的 Router-owned completion 進入記錄，R3 與未知 Side-effect 被排除，raw objective、path、secret 不會出現。檢視 aggregate metrics 與 correction rate。沒有 activation receipt 時維持 `intended-unverified`；缺少 receipt evidence 時 Skill consistency 必須為 unavailable。

## 3. 審查 Proposal

樣本具代表性後才切換 `reviewed`。逐一查看 Candidate evidence、精確 Profile Diff 與 Backtest；核准必須綁定同一份 preview。拒絕只 suppression 未變更的 evidence，不寫 Profile，也不改走 fallback。

## 4. 評估 Automatic Managed Promotion

多次 reviewed approval 都乾淨後，才考慮 `automatic`。自主順序為 `disabled < observe < reviewed < automatic`，且 **Workspace cannot elevate Personal**。自動寫入必須是 `automatic-managed`，target 只允許 `managed-personal`、`managed-workspace-local`；人工衝突會 suppression Candidate。

Automatic promotion 仍是明確觸發的本機 pass，必須顯示 notification，維持 **no background learning**、沒有 scheduler、沒有 telemetry；Runtime 與 Side-effect authority 不會因此提升。

## 5. 演練 Rollback 與 Purge

Rollback 會建立新的 reviewable forward Revision 並保留歷史。Purge 必須明確確認並綁定目前 Digest；history／analytics purge 不刪除 User-owned Profile。將模式改回 disabled 只停止後續 capture，不會暗中清除既有資料。

## 建議順序

採用 `observe -> reviewed -> automatic`，每次 transition 都保留人工 checkpoint。若 evidence、privacy 或 ownership 假設失效，立即回到 `disabled`。

`skill-only` 可以用本指南準備設定，但不能宣稱 durable Memory 或 MCP review transition；操作流程需要 Plugin + MCP。維持 **no telemetry**。

{COMMON_VOCAB_ZH}
''',
    )


def update_navigation_and_readmes() -> None:
    config = ROOT / "site" / "astro.config.mjs"
    text = config.read_text("utf-8")
    if "concepts/adaptive-workflow-memory" not in text:
        marker = "            { slug: 'concepts/personal-routing-profiles' },"
        if marker not in text:
            raise RuntimeError("Personal Profile navigation marker not found")
        text = text.replace(marker, marker + "\n            { slug: 'concepts/adaptive-workflow-memory' },", 1)
    if "guides/configure-workflow-memory" not in text:
        marker = "            { slug: 'guides/adoption' },"
        if marker not in text:
            raise RuntimeError("Guide navigation marker not found")
        text = text.replace(
            marker,
            marker + "\n            { slug: 'guides/configure-workflow-memory' },\n            { slug: 'guides/migrate-to-workflow-memory' },",
            1,
        )
    config.write_text(text, encoding="utf-8", newline="\n")

    upsert_marked(
        "README.md",
        "M4-B adaptive-memory",
        '''## Adaptive Workflow Memory

Adaptive Workflow Memory is an opt-in, local-first layer for turning repeated successful routes into reviewable managed Profiles. It is `default-off`: an upgrade does not start capture, create the Optional Memory DB, or modify a User-owned Profile.

Adopt it as `observe -> reviewed -> automatic`. Personal policy is the autonomy ceiling; Workspace policy can only reduce it. Automatic promotion writes only `automatic-managed` targets, has visible disclosure, and remains an explicit local pass with `no background learning` and no telemetry.

See `site/src/content/docs/concepts/adaptive-workflow-memory.md` and `site/src/content/docs/guides/configure-workflow-memory.md`.
''',
        before="## Real Model Evaluation",
    )
    upsert_marked(
        "README.zh-TW.md",
        "M4-B adaptive-memory",
        '''## Adaptive Workflow Memory

Adaptive Workflow Memory 是選擇加入、本機優先的路由記憶層，會把重複成功的路由整理成可審查的 Managed Profile。它維持 `default-off`：升級後不會自動 capture、不建立 Optional Memory DB，也不修改 User-owned Profile。

建議採 `observe -> reviewed -> automatic`。Personal Policy 是自主上限，Workspace 只能收緊。Automatic promotion 僅寫入 `automatic-managed` target，必須顯示通知，且仍是明確觸發的本機 pass，維持 `no background learning` 與 no telemetry。

完整說明位於 `site/src/content/docs/zh-tw/concepts/adaptive-workflow-memory.md` 與設定指南。
''',
        before="## Real Model Evaluation",
    )


COMMON_REFERENCE_EN = '''## Adaptive Workflow Memory public contract

The public surface contains **20** MCP tools. Memory uses a separate **Operational DB** and **Optional Memory DB**. Managed writes are limited to `managed-personal` and `managed-workspace-local`; User-owned Profile writes still require their original authority.

The four decisions remain separate: policy autonomy, trusted Workspace binding, Profile ownership/target authority, and Runtime/Side-effect execution authority. A trusted root is not a Host write grant.

**Skill consistency** is **unavailable** without **receipt evidence**. A planned route may be `intended-unverified`; it is not activation proof. The Memory Flight Recorder uses `fixture-trace` or sanitized runtime records. Its `deterministic-local-pilot` is **not Model Evidence** and never contains actual Personal Memory.
'''
COMMON_REFERENCE_ZH = '''## Adaptive Workflow Memory 公開契約

公開介面共有 **20** 個 MCP tools。Memory 將 **Operational DB** 與 **Optional Memory DB** 分開；Managed write 只允許 `managed-personal`、`managed-workspace-local`，User-owned Profile 仍保留原本的寫入權限邊界。

四項決策彼此獨立：Policy autonomy、可信 Workspace binding、Profile ownership／target authority，以及 Runtime／Side-effect execution authority。可信 root 不等於 Host write grant。

沒有 **receipt evidence** 時，**Skill consistency** 必須標示為 **unavailable**；`intended-unverified` 只是規劃意圖，不是 activation proof。Memory Flight Recorder 只使用 `fixture-trace` 或 sanitized runtime record；`deterministic-local-pilot` **not Model Evidence**，也不包含真實 Personal Memory。
'''


def update_references() -> None:
    english = (
        "site/src/content/docs/reference/cli.md",
        "site/src/content/docs/reference/local-state.md",
        "site/src/content/docs/reference/security-boundaries.md",
        "site/src/content/docs/reference/mcp-tools.mdx",
        "site/src/content/docs/showcase.md",
    )
    chinese = (
        "site/src/content/docs/zh-tw/reference/cli.md",
        "site/src/content/docs/zh-tw/reference/local-state.md",
        "site/src/content/docs/zh-tw/reference/security-boundaries.md",
        "site/src/content/docs/zh-tw/reference/mcp-tools.mdx",
        "site/src/content/docs/zh-tw/showcase.md",
    )
    for path in english:
        extra = COMMON_REFERENCE_EN
        if path.endswith("reference/cli.md"):
            extra += '''\n### CLI operations\n\nUse `memory status`, `memory policy validate`, `memory policy explain`, `memory remember`, `memory candidates rebuild|list|show|reject|promote-eligible`, `memory history summary|export|purge`, and the Profile Revision commands. `promote-eligible` is explicit local work, not a daemon.\n'''
        elif path.endswith("reference/local-state.md"):
            extra += '''\n### State separation\n\nThe Operational DB continues workflow/control state. The Optional Memory DB is lazily created only by enabled Memory writes. Managed Personal state, Workspace-Digest-scoped managed state and immutable Revision snapshots stay under the external data root; disabling capture does not silently purge them.\n'''
        elif path.endswith("reference/security-boundaries.md"):
            extra += '''\n### Authority decisions\n\n1. Personal Policy establishes the autonomy ceiling.\n2. Workspace Policy may reduce but cannot elevate it.\n3. Automatic materialization is managed-only and conflict-suppressed.\n4. Host Runtime, Skill activation, Side-effect and User-owned Workspace-file authority are never inferred from Memory.\n'''
        elif path.endswith("reference/mcp-tools.mdx"):
            extra += '''\n### Memory tool subset\n\nThe eight Memory tools are `get_memory_status`, `remember_workflow`, `record_route_feedback`, `list_workflow_candidates`, `preview_profile_update`, `transition_profile_update`, `rollback_profile_revision`, and `purge_workflow_memory`. Status/list/preview are read-only; transition/rollback remain conditional-local; purge is explicit and destructive.\n'''
        else:
            extra += '''\n### Flight Recorder and Pilot\n\nThe homepage presents five read-only sanitized scenarios—Policy Resolution, Observe, Reviewed Proposal, Automatic Managed Promotion and Purge—plus twenty deterministic local Pilot records: 6 Single, 8 Phased and 6 Goal-like, with at least eight Profile-assisted cases. The display is evidence literacy, not a product-performance claim.\n'''
        upsert_marked(path, "M4-B adaptive-memory-reference", extra)
    for path in chinese:
        extra = COMMON_REFERENCE_ZH
        if path.endswith("reference/cli.md"):
            extra += '''\n### CLI operations\n\n使用 `memory status`、`memory policy validate`、`memory policy explain`、`memory remember`、`memory candidates rebuild|list|show|reject|promote-eligible`、`memory history summary|export|purge` 與 Profile Revision commands。`promote-eligible` 是明確的本機操作，不是 daemon。\n'''
        elif path.endswith("reference/local-state.md"):
            extra += '''\n### State 分離\n\nOperational DB 保留 workflow／control state。Optional Memory DB 只在啟用 Memory 且進入寫入時才 lazy-create。Managed Personal、Workspace Digest scoped managed state 與 immutable Revision snapshot 位於外部 data root；關閉 capture 不會暗中 purge。\n'''
        elif path.endswith("reference/security-boundaries.md"):
            extra += '''\n### 四項 Authority 決策\n\n1. Personal Policy 決定 autonomy ceiling。\n2. Workspace Policy 只能降低，不能提升。\n3. Automatic materialization 僅限 managed target，遇衝突就 suppression。\n4. Memory 不會推導 Host Runtime、Skill activation、Side-effect 或 User-owned Workspace-file authority。\n'''
        elif path.endswith("reference/mcp-tools.mdx"):
            extra += '''\n### Memory tool subset\n\n八個 Memory tools：`get_memory_status`、`remember_workflow`、`record_route_feedback`、`list_workflow_candidates`、`preview_profile_update`、`transition_profile_update`、`rollback_profile_revision`、`purge_workflow_memory`。Status／list／preview 為唯讀；transition／rollback 維持 conditional-local；purge 必須明確確認且具破壞性。\n'''
        else:
            extra += '''\n### Flight Recorder 與 Pilot\n\n首頁提供五種唯讀 sanitized scenario：Policy Resolution、Observe、Reviewed Proposal、Automatic Managed Promotion、Purge；並提供二十筆 deterministic local Pilot record：6 Single、8 Phased、6 Goal-like，至少八筆使用 Profile。這是 evidence literacy，不是效能宣稱。\n'''
        upsert_marked(path, "M4-B adaptive-memory-reference", extra)


def recorder_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": "policy-resolution",
            "title": "Policy resolution",
            "title_zh_tw": "Policy 解析",
            "evidence_class": "fixture-trace",
            "summary": "Personal sets the ceiling; Workspace may only reduce it.",
            "summary_zh_tw": "Personal 決定上限，Workspace 只能收緊。",
            "events": [
                {"seq": 1, "event": "personal-policy", "state": "reviewed", "reason": "personal-ceiling"},
                {"seq": 2, "event": "workspace-policy", "state": "observe", "reason": "workspace-reduction"},
                {"seq": 3, "event": "effective-policy", "state": "observe", "reason": "workspace-cannot-elevate"},
            ],
        },
        {
            "id": "observe",
            "title": "Observe",
            "title_zh_tw": "Observe",
            "evidence_class": "sanitized-runtime-trace",
            "summary": "Eligible completion produces bounded metrics but no Profile proposal.",
            "summary_zh_tw": "符合條件的完成紀錄只產生有界指標，不建立 Profile proposal。",
            "events": [
                {"seq": 1, "event": "workflow-completed", "state": "eligible", "reason": "router-owned"},
                {"seq": 2, "event": "observation-recorded", "state": "redacted", "reason": "typed-fields-only"},
                {"seq": 3, "event": "profile-write", "state": "not-requested", "reason": "observe-ceiling"},
            ],
        },
        {
            "id": "reviewed-proposal",
            "title": "Reviewed proposal",
            "title_zh_tw": "Reviewed Proposal",
            "evidence_class": "sanitized-runtime-trace",
            "summary": "A bound preview is approved, revalidated and materialized as a managed Revision.",
            "summary_zh_tw": "綁定 preview 經核准與重新驗證後，成為 managed Revision。",
            "events": [
                {"seq": 1, "event": "candidate", "state": "proposed", "reason": "reviewed-threshold"},
                {"seq": 2, "event": "profile-preview", "state": "read-only", "reason": "exact-diff-backtest"},
                {"seq": 3, "event": "proposal", "state": "approved", "reason": "bound-review"},
                {"seq": 4, "event": "revision", "state": "managed-personal", "reason": "atomic-materialization"},
            ],
        },
        {
            "id": "automatic-managed-promotion",
            "title": "Automatic managed promotion",
            "title_zh_tw": "Automatic Managed Promotion",
            "evidence_class": "sanitized-runtime-trace",
            "summary": "High-confidence evidence writes only a managed target and emits visible disclosure.",
            "summary_zh_tw": "高信心證據只寫 managed target，並顯示可見通知。",
            "events": [
                {"seq": 1, "event": "candidate", "state": "high-confidence", "reason": "automatic-floor"},
                {"seq": 2, "event": "manual-conflict", "state": "clear", "reason": "pre-write-recheck"},
                {"seq": 3, "event": "profile", "state": "managed-workspace-local", "reason": "automatic-managed"},
                {"seq": 4, "event": "notification", "state": "visible", "reason": "mandatory-disclosure"},
            ],
        },
        {
            "id": "purge",
            "title": "Purge",
            "title_zh_tw": "Purge",
            "evidence_class": "fixture-trace",
            "summary": "Digest-bound deletion removes optional history while preserving Profiles and schema.",
            "summary_zh_tw": "Digest-bound deletion 只移除可選 history，保留 Profile 與 schema。",
            "events": [
                {"seq": 1, "event": "purge-request", "state": "confirmed", "reason": "current-summary-digest"},
                {"seq": 2, "event": "history", "state": "deleted", "reason": "history-only"},
                {"seq": 3, "event": "user-owned-profile", "state": "preserved", "reason": "ownership-boundary"},
                {"seq": 4, "event": "schema", "state": "preserved", "reason": "idempotent-purge"},
            ],
        },
    ]


def pilot_records() -> list[dict[str, Any]]:
    shapes = ["single"] * 6 + ["phased"] * 8 + ["goal-like"] * 6
    scenarios = [
        "default-off", "observe-metrics", "reviewed-approval", "correction",
        "automatic-managed-write", "suppression", "rollback", "purge",
        "observe-metrics", "reviewed-approval", "routing-consistency", "correction",
        "automatic-managed-write", "suppression", "routing-consistency", "rollback",
        "observe-metrics", "reviewed-approval", "routing-consistency", "purge",
    ]
    profile_indices = {2, 3, 5, 7, 8, 10, 11, 13, 14, 16, 18, 20}
    records: list[dict[str, Any]] = []
    for index, (shape, scenario) in enumerate(zip(shapes, scenarios, strict=True), start=1):
        profile_used = index in profile_indices
        if scenario == "default-off":
            mode = "disabled"
        elif scenario.startswith("observe"):
            mode = "observe"
        elif scenario in {"automatic-managed-write", "suppression"}:
            mode = "automatic"
        else:
            mode = "reviewed"
        target = "none"
        if profile_used:
            target = "managed-workspace-local" if index % 2 == 0 else "managed-personal"
        receipt = index in {3, 5, 8, 10, 13, 16, 18, 20}
        records.append(
            {
                "record_id": f"pilot-{index:02d}",
                "shape": shape,
                "scenario": scenario,
                "mode": mode,
                "profile_used": profile_used,
                "profile_target": target,
                "receipt_evidence": receipt,
                "skill_consistency": "available" if receipt else "unavailable",
                "evidence_class": "sanitized-runtime-trace" if index % 3 else "fixture-trace",
                "result": "verified-local" if scenario != "default-off" else "disabled-no-state",
            }
        )
    return records


def memory_schema() -> tuple[dict[str, Any], dict[str, Any]]:
    scenario_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "title", "title_zh_tw", "evidence_class", "summary", "summary_zh_tw", "events"],
        "properties": {
            "id": {"enum": ["policy-resolution", "observe", "reviewed-proposal", "automatic-managed-promotion", "purge"]},
            "title": {"type": "string", "minLength": 1},
            "title_zh_tw": {"type": "string", "minLength": 1},
            "evidence_class": {"enum": ["fixture-trace", "sanitized-runtime-trace"]},
            "summary": {"type": "string", "minLength": 1},
            "summary_zh_tw": {"type": "string", "minLength": 1},
            "events": {
                "type": "array", "minItems": 3, "maxItems": 6,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["seq", "event", "state", "reason"],
                    "properties": {
                        "seq": {"type": "integer", "minimum": 1},
                        "event": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                        "state": {"type": "string", "minLength": 1},
                        "reason": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                    },
                },
            },
        },
    }
    pilot_schema = {
        "type": "object", "additionalProperties": False,
        "required": ["pilot_id", "evidence_class", "claim", "summary", "records"],
        "properties": {
            "pilot_id": {"const": "adaptive-memory-local-pilot-v1"},
            "evidence_class": {"const": "deterministic-local-pilot"},
            "claim": {"const": "not-model-evidence"},
            "summary": {
                "type": "object", "additionalProperties": False,
                "required": ["total", "single", "phased", "goal_like", "profile_used"],
                "properties": {
                    "total": {"const": 20}, "single": {"const": 6}, "phased": {"const": 8},
                    "goal_like": {"const": 6}, "profile_used": {"type": "integer", "minimum": 8},
                },
            },
            "records": {
                "type": "array", "minItems": 20, "maxItems": 20,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": [
                        "record_id", "shape", "scenario", "mode", "profile_used", "profile_target",
                        "receipt_evidence", "skill_consistency", "evidence_class", "result",
                    ],
                    "properties": {
                        "record_id": {"type": "string", "pattern": "^pilot-[0-9]{{2}}$"},
                        "shape": {"enum": ["single", "phased", "goal-like"]},
                        "scenario": {"enum": [
                            "default-off", "observe-metrics", "reviewed-approval", "automatic-managed-write",
                            "correction", "suppression", "rollback", "purge", "routing-consistency",
                        ]},
                        "mode": {"enum": ["disabled", "observe", "reviewed", "automatic"]},
                        "profile_used": {"type": "boolean"},
                        "profile_target": {"enum": ["none", "managed-personal", "managed-workspace-local"]},
                        "receipt_evidence": {"type": "boolean"},
                        "skill_consistency": {"enum": ["available", "unavailable"]},
                        "evidence_class": {"enum": ["fixture-trace", "sanitized-runtime-trace"]},
                        "result": {"enum": ["verified-local", "disabled-no-state"]},
                    },
                },
            },
        },
    }
    return scenario_schema, pilot_schema


def update_demo_data() -> None:
    inputs_path = ROOT / "demo" / "v2-scenarios" / "inputs.json"
    schema_path = ROOT / "demo" / "v2-scenarios" / "schema.json"
    inputs = json.loads(inputs_path.read_text("utf-8"))
    records = pilot_records()
    inputs["memory_flight_recorder"] = recorder_scenarios()
    inputs["memory_pilot"] = {
        "pilot_id": "adaptive-memory-local-pilot-v1",
        "evidence_class": "deterministic-local-pilot",
        "claim": "not-model-evidence",
        "summary": {
            "total": 20,
            "single": 6,
            "phased": 8,
            "goal_like": 6,
            "profile_used": sum(bool(record["profile_used"]) for record in records),
        },
        "records": records,
    }
    write_json(inputs_path, inputs)

    schema = json.loads(schema_path.read_text("utf-8"))
    if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
        raise RuntimeError("Unexpected demo input schema root")
    scenario_schema, pilot_schema = memory_schema()
    schema["properties"]["memory_flight_recorder"] = {
        "type": "array", "minItems": 5, "maxItems": 5, "items": scenario_schema,
    }
    schema["properties"]["memory_pilot"] = pilot_schema
    required = schema.setdefault("required", [])
    for key in ("memory_flight_recorder", "memory_pilot"):
        if key not in required:
            required.append(key)
    write_json(schema_path, schema)

    generated = {
        "schema_version": "1.0.0",
        "evidence_boundary": {
            "label": "deterministic-local-pilot",
            "claim": "not-model-evidence",
            "contains_personal_memory": False,
            "background_learning": False,
            "telemetry": False,
        },
        "scenarios": inputs["memory_flight_recorder"],
        "pilot": inputs["memory_pilot"],
    }
    write_json("site/src/data/memory-flight-recorder.generated.json", generated)

    builder_path = ROOT / "scripts" / "build-v2-demo-data.py"
    builder = builder_path.read_text("utf-8")
    sentinel = "def _sync_m4b_memory_flight_recorder()"
    helper = r'''

# M4-B: keep the sanitized Memory Flight Recorder and local Pilot generated
# from the canonical demo input rather than hand-authored in the site bundle.
def _sync_m4b_memory_flight_recorder() -> None:
    import json as _m4b_json
    from pathlib import Path as _M4BPath
    import sys as _m4b_sys

    _root = _M4BPath(__file__).resolve().parents[1]
    _inputs = _m4b_json.loads(
        (_root / "demo" / "v2-scenarios" / "inputs.json").read_text("utf-8")
    )
    _payload = {
        "schema_version": "1.0.0",
        "evidence_boundary": {
            "label": "deterministic-local-pilot",
            "claim": "not-model-evidence",
            "contains_personal_memory": False,
            "background_learning": False,
            "telemetry": False,
        },
        "scenarios": _inputs["memory_flight_recorder"],
        "pilot": _inputs["memory_pilot"],
    }
    _rendered = _m4b_json.dumps(_payload, ensure_ascii=False, indent=2) + "\n"
    _target = _root / "site" / "src" / "data" / "memory-flight-recorder.generated.json"
    if "--check" in _m4b_sys.argv:
        if not _target.is_file() or _target.read_text("utf-8") != _rendered:
            raise SystemExit("Memory Flight Recorder generated data is stale")
        return
    _target.parent.mkdir(parents=True, exist_ok=True)
    _target.write_text(_rendered, encoding="utf-8", newline="\n")
'''
    if sentinel not in builder:
        markers = ('if __name__ == "__main__":', "if __name__ == '__main__':")
        marker = next((item for item in markers if item in builder), None)
        if marker is None:
            raise RuntimeError("build-v2-demo-data.py has no main guard")
        builder = builder.replace(marker, textwrap.dedent(helper).rstrip() + "\n\n" + marker, 1)
        main_line = marker + "\n"
        builder = builder.replace(main_line, main_line + "    _sync_m4b_memory_flight_recorder()\n", 1)
        builder_path.write_text(builder, encoding="utf-8", newline="\n")


def update_home_landing() -> None:
    path = ROOT / "site" / "src" / "components" / "HomeLanding.astro"
    text = path.read_text("utf-8")
    if "memory-flight-recorder.generated.json" not in text:
        if not text.startswith("---"):
            raise RuntimeError("HomeLanding.astro frontmatter not found")
        close = text.find("\n---", 3)
        if close < 0:
            raise RuntimeError("HomeLanding.astro frontmatter close not found")
        insertion = "\nimport memoryFlightRecorder from '../data/memory-flight-recorder.generated.json';\nconst m4bIsZh = Astro.currentLocale?.toLowerCase() === 'zh-tw';"
        text = text[:close] + insertion + text[close:]

    start = "<!-- M4-B memory-flight-recorder:start -->"
    end = "<!-- M4-B memory-flight-recorder:end -->"
    block = r'''
<!-- M4-B memory-flight-recorder:start -->
<section class="memory-flight-recorder" data-memory-flight-recorder aria-labelledby="memory-flight-recorder-title">
  <div class="memory-flight-recorder__intro">
    <h2 id="memory-flight-recorder-title">
      {m4bIsZh ? 'Memory Flight Recorder' : 'Memory Flight Recorder'}
    </h2>
    <p>
      {m4bIsZh
        ? '切換五種去識別情境，查看 Policy、提案、Managed Promotion 與 Purge 的公開安全事件。'
        : 'Switch between five sanitized scenarios to inspect public-safe Policy, proposal, managed-promotion and purge events.'}
    </p>
    <p class="memory-flight-recorder__boundary">
      <strong>deterministic-local-pilot</strong>
      <span>{m4bIsZh ? '不是 Model Evidence' : 'not Model Evidence'}</span>
    </p>
  </div>

  <div class="memory-flight-recorder__workspace">
    <div class="memory-flight-recorder__tabs" role="tablist" aria-label="Memory scenarios">
      {memoryFlightRecorder.scenarios.map((scenario, index) => (
        <button
          type="button"
          role="tab"
          aria-selected={index === 0 ? 'true' : 'false'}
          aria-controls={`memory-panel-${scenario.id}`}
          id={`memory-tab-${scenario.id}`}
          data-memory-tab={scenario.id}
        >
          {m4bIsZh ? scenario.title_zh_tw : scenario.title}
        </button>
      ))}
    </div>

    <div class="memory-flight-recorder__panels">
      {memoryFlightRecorder.scenarios.map((scenario, index) => (
        <article
          id={`memory-panel-${scenario.id}`}
          role="tabpanel"
          aria-labelledby={`memory-tab-${scenario.id}`}
          data-memory-panel={scenario.id}
          hidden={index !== 0}
        >
          <div class="memory-flight-recorder__panel-heading">
            <h3>{m4bIsZh ? scenario.title_zh_tw : scenario.title}</h3>
            <code>{scenario.evidence_class}</code>
          </div>
          <p>{m4bIsZh ? scenario.summary_zh_tw : scenario.summary}</p>
          <ol>
            {scenario.events.map((event) => (
              <li>
                <span>{String(event.seq).padStart(2, '0')}</span>
                <div>
                  <strong>{event.event}</strong>
                  <small>{event.state} · {event.reason}</small>
                </div>
              </li>
            ))}
          </ol>
        </article>
      ))}
    </div>
  </div>

  <dl class="memory-flight-recorder__pilot" aria-label="Deterministic local Pilot distribution">
    <div><dt>{m4bIsZh ? '總筆數' : 'Records'}</dt><dd>{memoryFlightRecorder.pilot.summary.total}</dd></div>
    <div><dt>Single</dt><dd>{memoryFlightRecorder.pilot.summary.single}</dd></div>
    <div><dt>Phased</dt><dd>{memoryFlightRecorder.pilot.summary.phased}</dd></div>
    <div><dt>Goal-like</dt><dd>{memoryFlightRecorder.pilot.summary.goal_like}</dd></div>
    <div><dt>{m4bIsZh ? '使用 Profile' : 'Profile-assisted'}</dt><dd>{memoryFlightRecorder.pilot.summary.profile_used}</dd></div>
  </dl>
</section>

<script>
  document.querySelectorAll('[data-memory-flight-recorder]').forEach((root) => {
    const tabs = Array.from(root.querySelectorAll('[data-memory-tab]'));
    const panels = Array.from(root.querySelectorAll('[data-memory-panel]'));
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const selected = tab.getAttribute('data-memory-tab');
        tabs.forEach((item) => item.setAttribute('aria-selected', item === tab ? 'true' : 'false'));
        panels.forEach((panel) => {
          panel.hidden = panel.getAttribute('data-memory-panel') !== selected;
        });
      });
    });
  });
</script>

<style>
  .memory-flight-recorder {
    width: min(1120px, calc(100% - 2rem));
    margin: clamp(4rem, 9vw, 8rem) auto;
    padding: clamp(1.25rem, 3vw, 2.5rem);
    border: 1px solid color-mix(in srgb, currentColor 16%, transparent);
    border-radius: 1.25rem;
    background: color-mix(in srgb, var(--sl-color-bg, #08111f) 94%, white 6%);
  }
  .memory-flight-recorder__intro { max-width: 48rem; }
  .memory-flight-recorder__intro h2 { margin: 0; font-size: clamp(2rem, 5vw, 3.8rem); line-height: .98; }
  .memory-flight-recorder__intro > p { max-width: 42rem; line-height: 1.7; }
  .memory-flight-recorder__boundary { display: flex; gap: .75rem; flex-wrap: wrap; align-items: baseline; }
  .memory-flight-recorder__boundary span { opacity: .72; }
  .memory-flight-recorder__workspace { display: grid; grid-template-columns: minmax(13rem, .72fr) minmax(0, 1.7fr); gap: 1rem; margin-top: 2rem; }
  .memory-flight-recorder__tabs { display: flex; flex-direction: column; gap: .5rem; }
  .memory-flight-recorder__tabs button {
    appearance: none; width: 100%; padding: .8rem .9rem; border: 1px solid color-mix(in srgb, currentColor 16%, transparent);
    border-radius: .7rem; background: transparent; color: inherit; text-align: left; font: inherit; font-size: .9rem; line-height: 1.3; cursor: pointer;
  }
  .memory-flight-recorder__tabs button[aria-selected='true'] { background: color-mix(in srgb, currentColor 10%, transparent); border-color: color-mix(in srgb, currentColor 38%, transparent); }
  .memory-flight-recorder__tabs button:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
  .memory-flight-recorder__panels article { min-height: 21rem; padding: clamp(1rem, 2.5vw, 1.6rem); border-radius: .9rem; background: color-mix(in srgb, currentColor 6%, transparent); }
  .memory-flight-recorder__panel-heading { display: flex; justify-content: space-between; gap: 1rem; align-items: baseline; }
  .memory-flight-recorder__panel-heading h3 { margin: 0; font-size: 1.25rem; }
  .memory-flight-recorder__panel-heading code { font-size: .72rem; }
  .memory-flight-recorder__panels ol { list-style: none; padding: 0; margin: 1.5rem 0 0; display: grid; gap: .65rem; }
  .memory-flight-recorder__panels li { display: grid; grid-template-columns: 2.25rem 1fr; gap: .7rem; align-items: start; padding: .75rem 0; border-top: 1px solid color-mix(in srgb, currentColor 12%, transparent); }
  .memory-flight-recorder__panels li > span { font-family: ui-monospace, monospace; opacity: .55; }
  .memory-flight-recorder__panels li strong, .memory-flight-recorder__panels li small { display: block; }
  .memory-flight-recorder__panels li small { margin-top: .2rem; opacity: .68; }
  .memory-flight-recorder__pilot { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .75rem; margin: 1rem 0 0; }
  .memory-flight-recorder__pilot div { padding: .9rem; border-top: 1px solid color-mix(in srgb, currentColor 18%, transparent); }
  .memory-flight-recorder__pilot dt { font-size: .75rem; opacity: .66; }
  .memory-flight-recorder__pilot dd { margin: .25rem 0 0; font-size: 1.35rem; font-weight: 700; }
  @media (max-width: 760px) {
    .memory-flight-recorder__workspace { grid-template-columns: 1fr; }
    .memory-flight-recorder__tabs { flex-direction: row; overflow-x: auto; padding-bottom: .35rem; }
    .memory-flight-recorder__tabs button { min-width: 10rem; }
    .memory-flight-recorder__pilot { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
</style>
<!-- M4-B memory-flight-recorder:end -->
'''
    block = textwrap.dedent(block).strip()
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if pattern.search(text):
        text = pattern.sub(block, text, count=1)
    else:
        marker = "</main>"
        if marker in text:
            position = text.rfind(marker)
            text = text[:position] + block + "\n\n" + text[position:]
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    package_policy_examples()
    add_example_inventories()
    publish_core_docs()
    update_navigation_and_readmes()
    update_references()
    update_demo_data()
    update_home_landing()


if __name__ == "__main__":
    main()

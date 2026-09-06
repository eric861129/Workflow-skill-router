import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { ListRootsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { MEMORY_TOOL_NAMES } from "../src/memory-tool-schemas.js";

const context = {session_id: "session-m1c", actor: "developer", runtime_policy_snapshot_id: "runtime-policy-m1c"};
// Synthetic local completion evidence; uses only the shipped Python runtime,
// so the same test also runs from the standalone Plugin distribution.
const seed = String.raw`
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.memory import (CompletedWorkflowReader, MatcherSeed, MemoryScope, MemoryStore,
    MemoryRequestContext, WorkflowMemoryService, build_route_observation)
from workflow_skill_router.memory.service import RememberWorkflowResult
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import (RequestContext, PlanWork, RoutingContextInput,
    NextWorkQuery, RecordWorkEvent, EvaluateGate)
from workflow_skill_router.workflow.local_observations import LocalProgressObservation
root = Path(sys.argv[1])
(root / "config").mkdir(exist_ok=True)
(root / "config/workflow-memory.json").write_text(json.dumps({
    "schema_id":"workflow-skill-router/memory-policy", "schema_version":"1.0.0",
    "artifact_kind":"memory-policy", "policy_id":"personal:mcp-fixture", "scope":"personal", "mode":"reviewed"
}), encoding="utf-8")
database = root / "router-v2.sqlite3"
context = RequestContext("session-m1c", "developer", "runtime-policy-m1c")
memory_context = MemoryRequestContext(context.session_id, context.actor, context.runtime_policy_snapshot_id)
local = LocalControlPlaneService(database)
memory = WorkflowMemoryService(database)
def digest(value): return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()
def completed_plan(key):
    plan = local.plan_work(PlanWork(context, "Synthetic API fixture", None, "single", ("skill:api-designer",), "only",
        0, key, key, RoutingContextInput(None, ("api",), ("mcp",))))
    item = local.get_next_work(NextWorkQuery(context, plan.workflow_run_id)).work_item
    checks = ("router-local-single-completed",)
    local.record_work_event(RecordWorkEvent(context, plan.workflow_run_id, item.phase_id,
        LocalProgressObservation(item.work_item_id,"start",(),None),None,1,key+"-start",key))
    local.record_work_event(RecordWorkEvent(context, plan.workflow_run_id, item.phase_id,
        LocalProgressObservation(item.work_item_id,"submit",checks,None),None,2,key+"-submit",key))
    local.evaluate_gate(EvaluateGate(context,plan.workflow_run_id,item.phase_id,3,1,
        digest({"evidence_class":"user-or-agent-reported-local","persisted_check_ids":list(checks)}),(),key+"-gate",key))
    return plan
for index in range(3):
    plan = completed_plan("seed-"+str(index))
    workflow = CompletedWorkflowReader(database).read(memory_context,plan.workflow_run_id)
    with memory.open_store_for_current_policy() as store:
        when = (datetime.now(timezone.utc)-timedelta(days=1+index%2)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        observation = build_route_observation(workflow,MatcherSeed(("student api",),("api",),(),"user-explicit"),
            store.current_policy_snapshot,target_profile_class="managed-personal",risk_class="r1",side_effect_outcome="none",observed_at=when)
        result = RememberWorkflowResult("recorded",observation.observation_id,observation.observation_digest,
            observation.route_signature_digest,store.current_policy_snapshot.policy_digest,"managed-personal",(),False)
        store.record_route_observation(observation_document=observation.to_dict(),result_document=result.to_dict(),
            idempotency_key="fixture-"+str(index),command_digest=digest({"fixture":index}))
candidate = memory.rebuild_candidates(MemoryScope.PERSONAL)[0]
plan = completed_plan("mcp-live-remember")
print(json.dumps({"candidate_id":candidate.candidate_id,"workflow_run_id":plan.workflow_run_id}))
`;

test("bundled MCP executes the eight Memory tools with explicit consent and no authority escalation", {timeout: 30_000}, async () => {
  const parent = path.resolve(import.meta.dirname, "..");
  const pluginRoot = path.basename(parent) === "mcp" ? path.resolve(parent, "..") : parent;
  const root = await mkdtemp(path.join(os.tmpdir(), "wsr-memory-mcp-"));
  const state = path.join(root, "state");
  const workspace = path.join(root, "workspace");
  await mkdir(state); await mkdir(workspace);
  const transport = new StdioClientTransport({
    command: process.execPath, args: [path.join(pluginRoot, "mcp/server.bundle.mjs")], cwd: pluginRoot,
    env: {...Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string,string] => typeof entry[1] === "string")),
      WORKFLOW_SKILL_ROUTER_DATA_DIR: state, WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS: ""},
    stderr: "pipe",
  });
  const client = new Client({name: "memory-runtime-test", version: "1.0.0"}, {capabilities: {roots: {listChanged: false}}});
  client.setRequestHandler(ListRootsRequestSchema, async () => ({roots: [{uri: pathToFileURL(workspace).href}]}));
  const call = async (name: string, args: Record<string, unknown>) => {
    const result = await client.callTool({name, arguments: {context, ...args}});
    assert.notEqual(result.isError, true, JSON.stringify(result));
    return result.structuredContent as Record<string, any>;
  };
  const mutation = (key: string) => ({idempotency_key: key, correlation_id: key});
  try {
    await client.connect(transport);
    const listed = await client.listTools();
    assert.equal(listed.tools.length, 20);
    for (const name of MEMORY_TOOL_NAMES) assert.ok(listed.tools.some((tool) => tool.name === name));
    const off = await call("get_memory_status", {workspace_root: null});
    assert.equal(off.effective_mode, "disabled");
    assert.equal(off.memory_store_exists, false);
    assert.equal(existsSync(path.join(state, "memory")), false);
    const trustedStatus = await call("get_memory_status", {workspace_root: workspace});
    assert.equal(trustedStatus.effective_mode, "disabled");
    const untrusted = await client.callTool({name: "get_memory_status", arguments: {context, workspace_root: root}});
    assert.equal(untrusted.isError, true);
    assert.ok(!JSON.stringify(untrusted).includes(root));
    const unknown = await client.callTool({name: "get_memory_status", arguments: {context, workspace_root: null, target_path: "arbitrary"}});
    assert.equal(unknown.isError, true);

    const prepared = spawnSync(process.platform === "win32" ? "python" : "python3", ["-c", seed, state], {
      encoding: "utf8", cwd: pluginRoot,
      env: {...process.env, PYTHONPATH: path.join(pluginRoot, "runtime/workflow_skill_router.pyz"), PYTHONUTF8: "1"},
    });
    assert.equal(prepared.status, 0, prepared.stderr);
    const fixture = JSON.parse(prepared.stdout);
    const remembered = await call("remember_workflow", {workspace_root: null, workflow_run_id: fixture.workflow_run_id,
      target_profile_class: "managed-personal", risk_class: "r1", side_effect_outcome: "none", one_shot: "remember-once", ...mutation("remember-live")});
    assert.equal(remembered.status, "recorded");
    const feedback = await call("record_route_feedback", {workspace_root: null, workflow_run_id: fixture.workflow_run_id,
      observation_id: remembered.observation_id, feedback_type: "accepted", reason_code: "user-accepted", correction_dimensions: [],
      original_route_digest: null, corrected_route_digest: null, ...mutation("feedback-live")});
    assert.equal(feedback.status, "recorded");
    const candidates = await call("list_workflow_candidates", {workspace_root: null, status: null, limit: 100});
    assert.ok(candidates.candidates.some((value: any) => value.candidate_id === fixture.candidate_id));
    const preview = await call("preview_profile_update", {workspace_root: null, candidate_id: fixture.candidate_id});
    assert.equal(preview.status, "previewed");
    assert.equal(existsSync(path.join(state,"profiles/managed/personal/adaptive-memory.json")), false);
    const approve = (proposal: Record<string, unknown>, key: string) => call("transition_profile_update", {
      workspace_root: null, proposal_id: proposal.proposal_id, expected_proposal_digest: proposal.proposal_digest,
      expected_profile_digest: proposal.expected_profile_digest, expected_state_version: proposal.state_version,
      action: "approve", ...mutation(key),
    });
    const applied = await approve(preview.proposal, "apply-live");
    assert.equal(applied.status, "applied");
    assert.equal(applied.authority_mode, "router-local");
    const replayed = await approve(preview.proposal, "apply-live");
    assert.equal(replayed.replayed, true);
    assert.equal(applied.revision_id, replayed.revision_id);
    const rollback = await call("rollback_profile_revision", {workspace_root: null, source_revision_id: applied.revision_id,
      expected_profile_digest: preview.proposal.proposed_profile_digest, ...mutation("rollback-live")});
    assert.equal(rollback.status, "pending");
    assert.equal((await approve(rollback.proposal, "apply-rollback-live")).status, "applied");
    // Privacy purge remains available after disabling capture. Its explicit
    // confirmation and global history Digest cannot be silently inferred.
    await writeFile(path.join(state,"config/workflow-memory.json"), JSON.stringify({
      schema_id: "workflow-skill-router/memory-policy", schema_version: "1.0.0", artifact_kind: "memory-policy",
      policy_id: "personal:mcp-disabled", scope: "personal", mode: "disabled",
    }));
    const status = await call("get_memory_status", {workspace_root: null});
    const refusal = await client.callTool({name: "purge_workflow_memory", arguments: {context, scope: "history-only",
      expected_summary_digest: status.history_summary_digest, include_managed_profiles: false, confirmed: false, ...mutation("refuse-purge")}});
    assert.equal(refusal.isError, true);
    const purged = await call("purge_workflow_memory", {scope: "history-only", expected_summary_digest: status.history_summary_digest,
      include_managed_profiles: false, confirmed: true, ...mutation("purge-live")});
    assert.equal(purged.status, "purged");
    assert.equal(purged.deleted_observations, 4);
    assert.equal((await call("get_memory_status", {workspace_root: null})).eligible_workflow_count, 0);
    assert.equal(existsSync(path.join(state,"profiles/managed/personal/adaptive-memory.json")), true);
  } finally {
    await client.close(); await transport.close();
    await rm(root, {recursive: true, force: true, maxRetries: 5, retryDelay: 100});
  }
});

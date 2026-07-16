import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import path from "node:path";
import { discoverPython } from "./python-discovery.js";
import { resolveState } from "./state-path.js";

type Pending = { resolve: (value: unknown) => void; reject: (reason: Error) => void; timer: NodeJS.Timeout };

export class CoreBridgeError extends Error {
  constructor(
    readonly code: string,
    readonly details: Record<string, unknown>,
  ) {
    super(code);
    this.name = "CoreBridgeError";
  }
}

export class CoreClient {
  private child?: ChildProcessWithoutNullStreams;
  private generation = 0;
  private sequence = 0;
  private pending = new Map<string, Pending>();
  private buffer = "";
  constructor(private readonly pluginRoot = path.resolve(import.meta.dirname, "..")) {}

  async start() {
    if (this.child) return;
    const python = await discoverPython(process.platform);
    const state = await resolveState(process.platform, this.pluginRoot);
    const pyz = path.join(this.pluginRoot, "runtime", "workflow_skill_router.pyz");
    this.generation += 1;
    this.child = spawn(python.command, [...python.prefixArgs, pyz, "serve-jsonl", "--database", state.database],
      {
        cwd: this.pluginRoot,
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
          PYTHONUTF8: "1",
        },
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
      });
    this.child.stdout.setEncoding("utf8");
    this.child.stdout.on("data", (chunk) => this.onData(chunk));
    this.child.stderr.on("data", (chunk) => process.stderr.write(chunk));
    this.child.once("exit", () => this.failGeneration(new Error("bridge-restarted"), false));
  }

  private onData(chunk: string) {
    this.buffer += chunk;
    for (;;) {
      const index = this.buffer.indexOf("\n"); if (index < 0) break;
      const line = this.buffer.slice(0, index); this.buffer = this.buffer.slice(index + 1);
      try {
        const response = JSON.parse(line); const pending = this.pending.get(response.request_id);
        if (!pending || !response.request_id.startsWith(`g${this.generation}:`)) continue;
        clearTimeout(pending.timer); this.pending.delete(response.request_id);
        response.ok
          ? pending.resolve(response.result)
          : pending.reject(new CoreBridgeError(
            response.error?.code ?? "bridge-error",
            response.error ?? { code: "bridge-error" },
          ));
      } catch { process.stderr.write("Workflow Skill Router：忽略無效 bridge 回應。\n"); }
    }
  }

  private failGeneration(error: Error, terminate: boolean) {
    const child = this.child; this.child = undefined; this.buffer = "";
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(error); }
    this.pending.clear(); if (terminate && child && !child.killed) child.kill();
  }

  async call(tool: string, arguments_: unknown, options: { signal?: AbortSignal } = {}) {
    await this.start(); const child = this.child!;
    const requestId = `g${this.generation}:${++this.sequence}`;
    const deadline = tool === "run_model_evaluation" ? 30 * 60_000 : 15_000;
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.failGeneration(new Error("bridge-timeout"), true), deadline);
      this.pending.set(requestId, { resolve, reject, timer });
      options.signal?.addEventListener("abort", () => this.failGeneration(new Error("cancelled"), true), { once: true });
      child.stdin.write(JSON.stringify({ request_id: requestId, tool, arguments: arguments_ }) + "\n");
    });
  }

  async close() { this.failGeneration(new Error("bridge-closed"), true); }
}

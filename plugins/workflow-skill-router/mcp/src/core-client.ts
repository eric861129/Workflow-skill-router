import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import path from "node:path";
import { discoverPython } from "./python-discovery.js";
import { resolveState } from "./state-path.js";

type Pending = {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timer: NodeJS.Timeout;
  signal?: AbortSignal;
  abortListener?: () => void;
};
type WriteState = {
  generation: number;
  queued: number;
  chain: Promise<void>;
  closed: boolean;
  drainWaiters: Set<(error: Error) => void>;
};
type BridgeSpawner = () => ChildProcessWithoutNullStreams | Promise<ChildProcessWithoutNullStreams>;
type CoreClientOptions = {
  requestTimeout?: (tool: string) => number;
  maxQueuedWrites?: number;
};
const DEFAULT_MAX_QUEUED_WRITES = 64;

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
  private startPromise?: Promise<void>;
  private generation = 0;
  private sequence = 0;
  private pending = new Map<string, Pending>();
  private writeState?: WriteState;
  private buffer = "";
  constructor(
    private readonly pluginRoot = path.resolve(import.meta.dirname, ".."),
    private readonly bridgeSpawner?: BridgeSpawner,
    private readonly options: CoreClientOptions = {},
  ) {}

  async start() {
    if (this.child) return;
    if (this.startPromise) return await this.startPromise;
    this.startPromise = this.startBridge();
    try {
      await this.startPromise;
    } finally {
      this.startPromise = undefined;
    }
  }

  private async startBridge() {
    const child = this.bridgeSpawner ? await this.bridgeSpawner() : await this.spawnBridge();
    this.generation += 1;
    const generation = this.generation;
    this.child = child;
    this.buffer = "";
    this.writeState = {
      generation,
      queued: 0,
      chain: Promise.resolve(),
      closed: false,
      drainWaiters: new Set(),
    };
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => this.onData(child, generation, chunk));
    child.stderr.on("data", (chunk) => {
      if (this.isActiveBridge(child, generation)) process.stderr.write(chunk);
    });
    let started = false;
    let resolveStartup!: () => void;
    let rejectStartup!: (error: Error) => void;
    const startup = new Promise<void>((resolve, reject) => {
      resolveStartup = resolve;
      rejectStartup = reject;
    });
    child.once("spawn", () => {
      started = true;
      resolveStartup();
    });
    child.once("error", (error) => {
      if (!started) rejectStartup(error);
      if (this.isActiveBridge(child, generation)) this.failGeneration(error, true);
    });
    for (const stream of [child.stdin, child.stdout, child.stderr]) {
      stream.on("error", (error) => {
        if (this.isActiveBridge(child, generation)) this.failGeneration(error, true);
      });
    }
    child.once("exit", () => {
      const error = new Error("bridge-restarted");
      if (!started) rejectStartup(error);
      if (this.isActiveBridge(child, generation)) this.failGeneration(error, false);
    });
    await startup;
  }

  private async spawnBridge() {
    const python = await discoverPython(process.platform);
    const state = await resolveState(process.platform, this.pluginRoot);
    const pyz = path.join(this.pluginRoot, "runtime", "workflow_skill_router.pyz");
    return spawn(python.command, [...python.prefixArgs, pyz, "serve-jsonl", "--database", state.database],
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
  }

  private isActiveBridge(child: ChildProcessWithoutNullStreams, generation: number) {
    return this.child === child && this.generation === generation;
  }

  private onData(child: ChildProcessWithoutNullStreams, generation: number, chunk: string) {
    if (!this.isActiveBridge(child, generation)) return;
    this.buffer += chunk;
    for (;;) {
      const index = this.buffer.indexOf("\n"); if (index < 0) break;
      const line = this.buffer.slice(0, index); this.buffer = this.buffer.slice(index + 1);
      try {
        const response = JSON.parse(line) as { request_id?: unknown; ok?: unknown; result?: unknown; error?: unknown };
        if (!response || typeof response.request_id !== "string" || typeof response.ok !== "boolean") {
          this.failGeneration(new Error("bridge-protocol-error"), true);
          return;
        }
        const pending = this.pending.get(response.request_id);
        if (!pending || !response.request_id.startsWith(`g${generation}:`)) continue;
        this.pending.delete(response.request_id);
        clearTimeout(pending.timer);
        pending.signal?.removeEventListener("abort", pending.abortListener!);
        response.ok
          ? pending.resolve(response.result)
          : pending.reject(new CoreBridgeError(
            typeof (response.error as { code?: unknown } | undefined)?.code === "string"
              ? (response.error as { code: string }).code
              : "bridge-error",
            response.error && typeof response.error === "object"
              ? response.error as Record<string, unknown>
              : { code: "bridge-error" },
          ));
      } catch {
        this.failGeneration(new Error("bridge-protocol-error"), true);
        return;
      }
    }
  }

  private failGeneration(error: Error, terminate: boolean) {
    const child = this.child;
    const writeState = this.writeState;
    this.child = undefined;
    this.writeState = undefined;
    this.buffer = "";
    if (writeState) {
      writeState.closed = true;
      for (const rejectDrainWaiter of writeState.drainWaiters) rejectDrainWaiter(error);
      writeState.drainWaiters.clear();
    }
    for (const requestId of this.pending.keys()) this.expireRequest(requestId, error);
    if (terminate && child && !child.killed) child.kill();
  }

  private expireRequest(requestId: string, error: Error) {
    const pending = this.pending.get(requestId);
    if (!pending) return;
    this.pending.delete(requestId);
    clearTimeout(pending.timer);
    pending.signal?.removeEventListener("abort", pending.abortListener!);
    pending.reject(error);
  }

  private requestTimeout(tool: string) {
    return this.options.requestTimeout?.(tool)
      ?? (tool === "run_model_evaluation" ? 30 * 60_000 : 15_000);
  }

  private queueWrite(
    child: ChildProcessWithoutNullStreams,
    generation: number,
    requestId: string,
    payload: string,
  ) {
    const writeState = this.writeState;
    if (!writeState || writeState.closed || writeState.generation !== generation
      || !this.isActiveBridge(child, generation)) {
      this.expireRequest(requestId, new Error("bridge-restarted"));
      return;
    }
    if (writeState.queued >= (this.options.maxQueuedWrites ?? DEFAULT_MAX_QUEUED_WRITES)) {
      this.expireRequest(requestId, new Error("bridge-write-queue-full"));
      return;
    }
    writeState.queued += 1;
    const write = async () => {
      try {
        if (!this.pending.has(requestId) || writeState.closed || !this.isActiveBridge(child, generation)) return;
        if (!child.stdin.write(payload)) await this.waitForDrain(child, generation, writeState);
      } catch (error) {
        if (this.isActiveBridge(child, generation) && !writeState.closed) {
          this.failGeneration(error instanceof Error ? error : new Error("bridge-write-failed"), true);
        }
      } finally {
        writeState.queued -= 1;
      }
    };
    const scheduled = writeState.chain.then(write, write);
    writeState.chain = scheduled.catch(() => undefined);
  }

  private async waitForDrain(
    child: ChildProcessWithoutNullStreams,
    generation: number,
    writeState: WriteState,
  ) {
    await new Promise<void>((resolve, reject) => {
      let finished = false;
      const cleanup = () => {
        child.stdin.removeListener("drain", onDrain);
        child.stdin.removeListener("error", onError);
        child.stdin.removeListener("close", onClose);
        writeState.drainWaiters.delete(onGenerationFailure);
      };
      const finish = (error?: Error) => {
        if (finished) return;
        finished = true;
        cleanup();
        error ? reject(error) : resolve();
      };
      const onDrain = () => finish();
      const onError = (error: Error) => finish(error);
      const onClose = () => finish(new Error("bridge-write-closed"));
      const onGenerationFailure = (error: Error) => finish(error);
      child.stdin.once("drain", onDrain);
      child.stdin.once("error", onError);
      child.stdin.once("close", onClose);
      writeState.drainWaiters.add(onGenerationFailure);
      if (writeState.closed || !this.isActiveBridge(child, generation)) {
        onGenerationFailure(new Error("bridge-restarted"));
      }
    });
  }

  async call(tool: string, arguments_: unknown, options: { signal?: AbortSignal } = {}) {
    await this.start(); const child = this.child!;
    const generation = this.generation;
    const requestId = `g${generation}:${++this.sequence}`;
    const deadline = this.requestTimeout(tool);
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.expireRequest(requestId, new Error("bridge-timeout")), deadline);
      const pending: Pending = { resolve, reject, timer };
      this.pending.set(requestId, pending);
      if (options.signal) {
        pending.signal = options.signal;
        pending.abortListener = () => this.expireRequest(requestId, new Error("cancelled"));
        options.signal.addEventListener("abort", pending.abortListener, { once: true });
        if (options.signal.aborted) {
          pending.abortListener();
          return;
        }
      }
      this.queueWrite(child, generation, requestId, JSON.stringify({ request_id: requestId, tool, arguments: arguments_ }) + "\n");
    });
  }

  async close() { this.failGeneration(new Error("bridge-closed"), true); }
}

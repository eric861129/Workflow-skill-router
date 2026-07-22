import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { CoreClient } from "../src/core-client.js";

type BridgeRequest = { request_id: string; tool: string; arguments: unknown };

class FakeReadable extends EventEmitter {
  setEncoding(_encoding: BufferEncoding) {}
}

class FakeWritable extends EventEmitter {
  readonly writes: BridgeRequest[] = [];
  writeFailure?: Error;
  backpressureWrites = 0;

  write(payload: string) {
    if (this.writeFailure) throw this.writeFailure;
    this.writes.push(JSON.parse(payload) as BridgeRequest);
    if (this.backpressureWrites > 0) {
      this.backpressureWrites -= 1;
      return false;
    }
    return true;
  }
}

class FakeChild extends EventEmitter {
  readonly stdin = new FakeWritable();
  readonly stdout = new FakeReadable();
  readonly stderr = new FakeReadable();
  killed = false;

  kill() {
    this.killed = true;
    return true;
  }

  respond(requestId: string, result: unknown) {
    this.stdout.emit("data", `${JSON.stringify({ request_id: requestId, ok: true, result })}\n`);
  }
}

class ManualAbortSignal {
  aborted = false;
  private readonly listeners = new Set<() => void>();

  get listenerCount() { return this.listeners.size; }

  addEventListener(type: string, listener: () => void) {
    if (type === "abort") this.listeners.add(listener);
  }

  removeEventListener(type: string, listener: () => void) {
    if (type === "abort") this.listeners.delete(listener);
  }

  abort() {
    this.aborted = true;
    for (const listener of this.listeners) listener();
  }
}

function createClientWithSpawner(
  spawnBridge: () => ChildProcessWithoutNullStreams | Promise<ChildProcessWithoutNullStreams>,
  requestTimeout: (tool: string) => number,
  maxQueuedWrites?: number,
) {
  const client = new CoreClient("/fake-plugin", spawnBridge, { requestTimeout, maxQueuedWrites });
  // The test seam must be in place before start(), so these tests never launch Python.
  assert.equal((client as unknown as { bridgeSpawner?: unknown }).bridgeSpawner, spawnBridge);
  return client;
}

function createClient(
  child: FakeChild,
  requestTimeout: (tool: string) => number,
  emitSpawn = true,
  maxQueuedWrites?: number,
) {
  return createClientWithSpawner(async () => {
    if (emitSpawn) setImmediate(() => child.emit("spawn"));
    return child as unknown as ChildProcessWithoutNullStreams;
  }, requestTimeout, maxQueuedWrites);
}

test("start rejects when the child emits an error before startup completes", async () => {
  const child = new FakeChild();
  const client = createClient(child, () => 1_000, false);
  const starting = client.start();
  await new Promise<void>((resolve) => setImmediate(resolve));
  child.emit("error", new Error("bridge-spawn-failed"));

  await assert.rejects(starting, /bridge-spawn-failed/);
  assert.equal(child.killed, true);
});

test("stale child output and stream errors cannot corrupt a new generation", async () => {
  const staleChild = new FakeChild();
  const currentChild = new FakeChild();
  const children = [staleChild, currentChild];
  const client = createClientWithSpawner(async () => {
    const child = children.shift();
    if (!child) throw new Error("missing-fake-child");
    setImmediate(() => child.emit("spawn"));
    return child as unknown as ChildProcessWithoutNullStreams;
  }, () => 1_000);
  await client.start();

  const staleRequest = client.call("stale", {});
  void staleRequest.catch(() => {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  staleChild.emit("exit", 1, null);
  await assert.rejects(staleRequest, /bridge-restarted/);

  await client.start();
  const currentRequest = client.call("current", {});
  void currentRequest.catch(() => {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  const currentRequestId = currentChild.stdin.writes[0].request_id;

  staleChild.stdout.emit("data", "{\"request_id\":");
  for (const stream of [staleChild.stdin, staleChild.stdout, staleChild.stderr]) {
    assert.doesNotThrow(() => stream.emit("error", new Error("stale-stream-error")));
  }
  currentChild.respond(currentRequestId, { current: true });

  assert.deepEqual(await currentRequest, { current: true });
});

test("current stream errors fail the active generation and remain handled", async () => {
  const streams: Array<readonly [string, (child: FakeChild) => EventEmitter]> = [
    ["stdin", (child) => child.stdin],
    ["stdout", (child) => child.stdout],
    ["stderr", (child) => child.stderr],
  ];
  for (const [name, streamFor] of streams) {
    const child = new FakeChild();
    const client = createClient(child, () => 1_000);
    await client.start();
    const request = client.call(name, {});
    void request.catch(() => {});
    await new Promise<void>((resolve) => setImmediate(resolve));
    const error = new Error(`${name}-stream-error`);
    let emittedError: unknown;
    try {
      streamFor(child).emit("error", error);
    } catch (caught) {
      emittedError = caught;
    }

    if (emittedError) {
      await client.close();
      await assert.rejects(request, /bridge-closed/);
      assert.fail(emittedError);
    }
    await assert.rejects(request, new RegExp(`${name}-stream-error`));
    assert.doesNotThrow(() => streamFor(child).emit("error", error));
    assert.equal(child.killed, true);
  }
});

test("backpressure waits for drain before writing the next request", async () => {
  const child = new FakeChild();
  child.stdin.backpressureWrites = 1;
  const client = createClient(child, () => 1_000);
  await client.start();

  const first = client.call("first", {});
  void first.catch(() => {});
  const second = client.call("second", {});
  void second.catch(() => {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(child.stdin.writes.length, 1);
  assert.equal(child.stdin.writes[0].tool, "first");

  child.stdin.emit("drain");
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(child.stdin.writes.length, 2);
  assert.equal(child.stdin.writes[1].tool, "second");
  child.respond(child.stdin.writes[1].request_id, { order: 2 });
  child.respond(child.stdin.writes[0].request_id, { order: 1 });

  assert.deepEqual(await first, { order: 1 });
  assert.deepEqual(await second, { order: 2 });
});

test("backpressure rejects writes beyond the bounded queue", async () => {
  const child = new FakeChild();
  child.stdin.backpressureWrites = 1;
  const client = createClient(child, () => 1_000, true, 1);
  await client.start();

  const first = client.call("first", {});
  void first.catch(() => {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  const rejected = client.call("rejected", {});
  void rejected.catch(() => {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  if (child.stdin.writes.length !== 1) {
    await client.close();
    await assert.rejects(first, /bridge-closed/);
    await assert.rejects(rejected, /bridge-closed/);
    assert.fail("A blocked writable must not accept unbounded queued writes.");
  }
  await assert.rejects(rejected, /bridge-write-queue-full/);
  child.stdin.emit("drain");
  child.respond(child.stdin.writes[0].request_id, { accepted: true });
  assert.deepEqual(await first, { accepted: true });
});

test("a blocked writable close fails the active generation", async () => {
  const child = new FakeChild();
  child.stdin.backpressureWrites = 1;
  const client = createClient(child, () => 1_000);
  await client.start();

  const request = client.call("blocked", {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  child.stdin.emit("close");

  await assert.rejects(request, /bridge-write-closed/);
  assert.equal(child.killed, true);
});

test("a timed out request rejects alone and ignores its late response", async () => {
  const child = new FakeChild();
  const client = createClient(child, (tool) => tool === "slow" ? 1 : 1_000);
  await client.start();

  const slow = client.call("slow", {});
  const slowRejection = assert.rejects(slow, /bridge-timeout/);
  const fast = client.call("fast", {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  const [slowRequest, fastRequest] = child.stdin.writes;

  await slowRejection;
  let fastSettled = false;
  void fast.then(() => { fastSettled = true; });
  child.respond(slowRequest.request_id, { ignored: true });
  await Promise.resolve();
  assert.equal(fastSettled, false);
  child.respond(fastRequest.request_id, { accepted: true });
  assert.deepEqual(await fast, { accepted: true });
});

test("an aborted request rejects alone and removes its abort listener", async () => {
  const child = new FakeChild();
  const client = createClient(child, () => 1_000);
  const signal = new ManualAbortSignal();
  await client.start();

  const cancelled = client.call("cancelled", {}, { signal: signal as unknown as AbortSignal });
  const retained = client.call("retained", {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  const retainedRequest = child.stdin.writes[1];
  signal.abort();

  await assert.rejects(cancelled, /cancelled/);
  assert.equal(signal.listenerCount, 0);
  child.respond(retainedRequest.request_id, { accepted: true });
  assert.deepEqual(await retained, { accepted: true });
});

test("a child exit rejects every request in the active generation", async () => {
  const child = new FakeChild();
  const client = createClient(child, () => 1_000);
  await client.start();

  const first = client.call("first", {});
  const second = client.call("second", {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  child.emit("exit", 1, null);

  await assert.rejects(first, /bridge-restarted/);
  await assert.rejects(second, /bridge-restarted/);
});

test("a child transport error rejects every request in the active generation", async () => {
  const child = new FakeChild();
  const client = createClient(child, () => 1_000);
  await client.start();

  const first = client.call("first", {});
  void first.catch(() => {});
  const second = client.call("second", {});
  void second.catch(() => {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  let emittedError: unknown;
  try {
    child.emit("error", new Error("bridge-spawn-failed"));
  } catch (error) {
    emittedError = error;
  }

  if (emittedError) {
    await client.close();
    await assert.rejects(first, /bridge-closed/);
    await assert.rejects(second, /bridge-closed/);
    assert.fail(emittedError);
  }

  await assert.rejects(first, /bridge-spawn-failed/);
  await assert.rejects(second, /bridge-spawn-failed/);
  assert.equal(child.killed, true);
});

test("a malformed bridge response fails the active generation", async () => {
  const child = new FakeChild();
  const client = createClient(child, () => 50);
  await client.start();

  const request = client.call("first", {});
  void request.catch(() => {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  child.stdout.emit("data", "{invalid json}\n");

  if (!child.killed) {
    await client.close();
    await assert.rejects(request, /bridge-closed/);
    assert.fail("A malformed response must fail the active bridge generation.");
  }
  await assert.rejects(request, /bridge-protocol-error/);
});

test("a stdin write failure fails every request in the active generation", async () => {
  const child = new FakeChild();
  const client = createClient(child, () => 1_000);
  await client.start();

  const waiting = client.call("waiting", {});
  await new Promise<void>((resolve) => setImmediate(resolve));
  child.stdin.writeFailure = new Error("stdin-write-failed");
  const failedWrite = client.call("write-failure", {});

  await assert.rejects(waiting, /stdin-write-failed/);
  await assert.rejects(failedWrite, /stdin-write-failed/);
  assert.equal(child.killed, true);
});

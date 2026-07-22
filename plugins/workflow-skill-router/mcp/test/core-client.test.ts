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

  write(payload: string) {
    if (this.writeFailure) throw this.writeFailure;
    this.writes.push(JSON.parse(payload) as BridgeRequest);
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

function createClient(child: FakeChild, requestTimeout: (tool: string) => number) {
  const spawnBridge = async () => child as unknown as ChildProcessWithoutNullStreams;
  const client = new CoreClient("/fake-plugin", spawnBridge, { requestTimeout });
  // The test seam must be in place before start(), so these tests never launch Python.
  assert.equal((client as unknown as { bridgeSpawner?: unknown }).bridgeSpawner, spawnBridge);
  return client;
}

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

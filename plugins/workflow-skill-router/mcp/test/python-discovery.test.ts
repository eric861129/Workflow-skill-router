import assert from "node:assert/strict";
import test from "node:test";
import { candidates, discoverPython, PythonDiscoveryError } from "../src/python-discovery.js";

test("Python discovery order, minimum version, and typed unavailability", async () => {
  assert.deepEqual(candidates("win32"), [{ command: "py", prefixArgs: ["-3.11"] }, { command: "python", prefixArgs: [] }]);
  assert.deepEqual(candidates("linux"), [{ command: "python3", prefixArgs: [] }, { command: "python", prefixArgs: [] }]);
  await assert.rejects(
    discoverPython("linux", async () => "3.10", undefined),
    { name: "PythonDiscoveryError", message: "python-3.11-unavailable" },
  );
  assert.equal((await discoverPython("linux", async () => "3.11", undefined)).command, "python3");
});

test("explicit override is one executable without shell parsing", async () => {
  const seen: string[] = [];
  const result = await discoverPython("win32", async (candidate) => { seen.push(candidate.command); return "3.12"; }, "C:/Python/python.exe --bad");
  assert.deepEqual(seen, ["C:/Python/python.exe --bad"]); assert.deepEqual(result.prefixArgs, []);
});

test("Python discovery preserves OS execution errors when no version probe succeeds", async () => {
  for (const code of ["ENOENT", "EACCES", "EPERM"]) {
    const executionError = Object.assign(new Error(`spawn failed: ${code}`), { code });
    await assert.rejects(
      discoverPython("linux", async () => { throw executionError; }, undefined),
      (error: unknown) => error === executionError,
      code,
    );
  }
});

test("Python discovery keeps searching after an OS execution error when another candidate is valid", async () => {
  const executionError = Object.assign(new Error("spawn failed: ENOENT"), { code: "ENOENT" });
  const seen: string[] = [];
  const result = await discoverPython("linux", async (candidate) => {
    seen.push(candidate.command);
    if (candidate.command === "python3") throw executionError;
    return "3.11";
  }, undefined);

  assert.deepEqual(seen, ["python3", "python"]);
  assert.equal(result.command, "python");
});

test("Python discovery emits typed guidance only after a successful unsupported version probe", async () => {
  await assert.rejects(
    discoverPython("linux", async () => "3.10", undefined),
    PythonDiscoveryError,
  );
  await assert.rejects(
    discoverPython("linux", async () => "not-a-version", undefined),
    /python-version-probe-invalid/,
  );
});

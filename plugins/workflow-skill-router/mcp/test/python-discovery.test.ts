import assert from "node:assert/strict";
import test from "node:test";
import { candidates, discoverPython } from "../src/python-discovery.js";

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

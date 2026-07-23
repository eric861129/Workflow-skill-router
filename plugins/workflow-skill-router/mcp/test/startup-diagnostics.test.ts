import assert from "node:assert/strict";
import test from "node:test";
import { PythonDiscoveryError } from "../src/python-discovery.js";
import {
  GENERIC_STARTUP_FAILURE,
  PYTHON_STARTUP_FAILURE,
  startupFailureMessage,
} from "../src/startup-diagnostics.js";

test("only a typed Python discovery failure receives Python guidance", () => {
  assert.equal(startupFailureMessage(new PythonDiscoveryError()), PYTHON_STARTUP_FAILURE);
});

test("spawn OS errors receive generic startup remediation", () => {
  for (const code of ["ENOENT", "EACCES", "EPERM"]) {
    const error = Object.assign(new Error(`spawn failed: ${code}`), {
      code,
      syscall: "spawn python",
    });
    assert.equal(startupFailureMessage(error), GENERIC_STARTUP_FAILURE);
  }
});

#!/usr/bin/env node
// Test-only stdio proxy for the host-fault lane. It sits between a Host's MCP
// client and the real Router server, forwards every JSON-RPC message, and
// answers one named tool with the same error envelope the server uses for a
// capability-unavailable bridge error (see mcp/src/server.ts). Nothing here
// ships in a Plugin; the lane stages it into a per-case Plugin copy.
//
//   node fault_proxy.mjs --fault tool-failure --tool plan_work -- node server.bundle.mjs
//   node fault_proxy.mjs --fault passthrough -- node server.bundle.mjs
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

const FAULTS = new Set(["passthrough", "tool-failure"]);

function parseArguments(argv) {
  const options = { fault: "passthrough", tool: "plan_work", upstream: [] };
  let index = 0;
  while (index < argv.length) {
    const argument = argv[index];
    if (argument === "--") {
      options.upstream = argv.slice(index + 1);
      break;
    }
    if (argument === "--fault" || argument === "--tool") {
      const value = argv[index + 1];
      if (value === undefined) throw new Error(`${argument} needs a value`);
      options[argument.slice(2)] = value;
      index += 2;
      continue;
    }
    throw new Error(`unknown argument: ${argument}`);
  }
  if (!FAULTS.has(options.fault)) throw new Error(`unknown fault: ${options.fault}`);
  if (options.upstream.length === 0) throw new Error("upstream command required after --");
  return options;
}

function injectedToolFailure(id, tool) {
  const details = {
    code: "capability-unavailable",
    message: `Router tool ${tool} is unavailable in this session.`,
    fallback_action: "Router MCP planning did not complete.",
    injected_fault: "tool-failure",
  };
  return {
    jsonrpc: "2.0",
    id,
    result: {
      isError: true,
      content: [{ type: "text", text: JSON.stringify(details) }],
    },
  };
}

const options = parseArguments(process.argv.slice(2));
const [command, ...commandArguments] = options.upstream;
const upstream = spawn(command, commandArguments, {
  stdio: ["pipe", "pipe", "pipe"],
  env: process.env,
  windowsHide: true,
});

let closing = false;
upstream.stdout.pipe(process.stdout);
upstream.stderr.pipe(process.stderr);
upstream.once("exit", (code, signal) => {
  // A signal we sent during our own shutdown is a clean exit, not a failure.
  process.exitCode = closing ? 0 : code ?? (signal ? 1 : 0);
  process.stdin.pause();
});
upstream.once("error", (error) => {
  process.stderr.write(`fault_proxy: upstream failed to start: ${error.message}\n`);
  process.exit(1);
});

const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
input.on("line", (line) => {
  let message;
  try {
    message = JSON.parse(line);
  } catch {
    upstream.stdin.write(`${line}\n`);
    return;
  }
  const isTargetCall =
    options.fault === "tool-failure" &&
    message?.method === "tools/call" &&
    message?.params?.name === options.tool &&
    message.id !== undefined;
  if (isTargetCall) {
    process.stdout.write(`${JSON.stringify(injectedToolFailure(message.id, options.tool))}\n`);
    return;
  }
  upstream.stdin.write(`${line}\n`);
});
// The real server keeps its Python bridge open after stdin closes and only
// shuts down on a signal, so mirror what a Host does: end stdin, then signal.
function shutdown(signal = "SIGTERM") {
  closing = true;
  if (upstream.exitCode === null && upstream.signalCode === null) {
    upstream.stdin.end();
    setTimeout(() => {
      if (upstream.exitCode === null && upstream.signalCode === null) upstream.kill(signal);
    }, 1500).unref();
  }
}
input.once("close", () => shutdown());
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    shutdown(signal);
    upstream.once("exit", () => process.exit(0));
  });
}

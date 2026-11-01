// Minimal stdio MCP server used only to test fault_proxy.mjs forwarding.
import { createInterface } from "node:readline";

const TOOLS = [{ name: "plan_work" }, { name: "get_router_status" }];

function reply(id, result) {
  process.stdout.write(`${JSON.stringify({ jsonrpc: "2.0", id, result })}\n`);
}

const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
input.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.id === undefined) return;
  if (message.method === "initialize") {
    reply(message.id, {
      protocolVersion: "2025-06-18",
      capabilities: { tools: {} },
      serverInfo: { name: "fake-router", version: "0.0.0" },
    });
  } else if (message.method === "tools/list") {
    reply(message.id, { tools: TOOLS });
  } else if (message.method === "tools/call") {
    reply(message.id, { content: [{ type: "text", text: `ok:${message.params.name}` }] });
  } else {
    process.stdout.write(`${JSON.stringify({ jsonrpc: "2.0", id: message.id, error: { code: -32601, message: "unknown" } })}\n`);
  }
});
input.once("close", () => process.exit(0));

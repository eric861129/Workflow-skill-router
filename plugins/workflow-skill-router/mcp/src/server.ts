import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import path from "node:path";
import { CoreBridgeError, CoreClient } from "./core-client.js";
import { TOOL_DEFINITIONS } from "./tool-definitions.js";
import {
  WorkspaceRootTrustError,
  bindPlanWorkWorkspaceRoot,
  collectTrustedWorkspaceRoots,
} from "./workspace-roots.js";

const core = new CoreClient();
try { await core.start(); } catch {
  process.stderr.write("Workflow Skill Router：Python runtime 不可用，切換為 skill-only-fallback。\n");
  process.exit(78);
}
const server = new McpServer({ name: "workflow-skill-router", version: "2.0.0-beta.3" });
const trustedWorkspaceRoots = async () => {
  let clientRoots: { uri: string }[] = [];
  if (server.server.getClientCapabilities()?.roots) {
    try {
      clientRoots = (await server.server.listRoots(undefined, { timeout: 2_000 })).roots;
    } catch {
      clientRoots = [];
    }
  }
  const configured = (process.env.WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS ?? "")
    .split(path.delimiter)
    .filter(Boolean);
  return collectTrustedWorkspaceRoots(clientRoots, configured);
};
for (const definition of TOOL_DEFINITIONS) {
  server.registerTool(definition.name, {
    title: definition.title,
    description: definition.description,
    inputSchema: definition.inputSchema,
    outputSchema: definition.outputSchema,
    annotations: definition.annotations,
  },
    async (arguments_: unknown) => {
      try {
        const boundArguments = definition.name === "plan_work"
          ? bindPlanWorkWorkspaceRoot(
            arguments_ as Record<string, unknown>,
            await trustedWorkspaceRoots(),
          )
          : arguments_;
        const result = await core.call(definition.name, boundArguments);
        return {
          content: [{ type: "text" as const, text: JSON.stringify(result) }],
          structuredContent: result as Record<string, unknown>,
        };
      } catch (error) {
        if (error instanceof CoreBridgeError && error.code === "capability-unavailable") {
          return {
            isError: true,
            content: [{ type: "text" as const, text: JSON.stringify(error.details) }],
          };
        }
        if (error instanceof WorkspaceRootTrustError) {
          return {
            isError: true,
            content: [{ type: "text" as const, text: JSON.stringify({
              code: error.code,
              message: error.message,
              fallback_action: "Use an MCP Client root, configure WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS, or omit workspace_root.",
            }) }],
          };
        }
        throw error;
      }
    });
}
process.once("SIGINT", async () => { await core.close(); process.exit(0); });
process.once("SIGTERM", async () => { await core.close(); process.exit(0); });
await server.connect(new StdioServerTransport());

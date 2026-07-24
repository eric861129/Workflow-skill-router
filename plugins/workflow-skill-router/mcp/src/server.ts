import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import path from "node:path";
import { CfWorkerJsonSchemaValidator } from "./cfworker-json-schema-provider.js";
import { CoreBridgeError, CoreClient } from "./core-client.js";
import { startupFailureMessage } from "./startup-diagnostics.js";
import { TOOL_DEFINITIONS } from "./tool-definitions.js";
import { TOOL_OUTPUT_SCHEMAS } from "./tool-output-schemas.js";
import { PLAN_WORK_INPUT_SCHEMA } from "./tool-schemas.js";
import {
  WorkspaceRootTrustError,
  bindPlanWorkWorkspaceRoot,
  collectTrustedWorkspaceRoots,
} from "./workspace-roots.js";

export const MCP_SERVER_VERSION = "2.0.2";

const core = new CoreClient();
try { await core.start(); } catch (error) {
  process.stderr.write(startupFailureMessage(error));
  process.exit(78);
}
const server = new McpServer(
  { name: "workflow-skill-router", version: MCP_SERVER_VERSION },
  { jsonSchemaValidator: new CfWorkerJsonSchemaValidator() },
);
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
        // MCP SDK registration accepts object shapes; parse after root binding to
        // enforce plan_work cross-field constraints declared with superRefine.
        const validatedArguments = definition.name === "plan_work"
          ? PLAN_WORK_INPUT_SCHEMA.parse(boundArguments)
          : boundArguments;
        const rawResult = await core.call(definition.name, validatedArguments);
        const result = TOOL_OUTPUT_SCHEMAS[definition.name].parse(rawResult);
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
